"""Pure deterministic simulated-order creation and terminal resolution for Phase 6.1."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Context, Decimal, localcontext
from enum import StrEnum
from threading import Lock
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_trading_scanner.domain import (
    AccountId,
    AgentId,
    AllocationId,
    MarketEventId,
    OrchestrationResultId,
    OrderCancellationCommandId,
    OrderCreationCommandId,
    OrderCreationReceiptId,
    OrderProjectionId,
    OrderTerminalResolutionId,
    ReplayArtifactId,
    ReplayScheduleId,
    ReservationId,
    RiskDecisionId,
    SimulatedOrderId,
    SimulationExecutionModelId,
    SimulationLiquidityModelId,
    SimulationRunId,
    StrategyDecisionId,
    TradeProposalId,
)
from ai_trading_scanner.domain.content_identity import canonical_json_bytes_v2, sha256_content_id_v2
from ai_trading_scanner.domain.execution import ExecutionEnvironment, SubmissionMode
from ai_trading_scanner.market_data import (
    CanonicalDataset,
    HistoricalBar,
    TradingSession,
    UsEquitiesCalendar,
)
from ai_trading_scanner.risk import ReservationAttemptStatus
from ai_trading_scanner.simulation.artifacts import (
    ExecutionResolutionOutcome,
    ExecutionResolutionPayload,
    ExecutionResolutionReason,
    ReplayArtifactBundle,
    calculate_marker_payload_id,
)
from ai_trading_scanner.simulation.models import (
    MarketEventReference,
    SimulatedOrder,
    SimulatedOrderSide,
    SimulatedOrderType,
    SimulationExecutionConfiguration,
    SimulationLiquidityConfiguration,
    calculate_simulated_order_id,
)
from ai_trading_scanner.simulation.orchestration import (
    CausalOrchestrationResult,
    CausalOrchestrator,
    OrchestrationMarketView,
    OrchestrationOutcome,
)
from ai_trading_scanner.simulation.scheduler import ReplaySchedule
from ai_trading_scanner.strategies import TradeProposalDecision


def _without_id(value: BaseModel | dict[str, object], field: str) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude={field})
    return {key: item for key, item in value.items() if key != field}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _reject_float(value: object, label: str) -> object:
    if isinstance(value, float):
        raise ValueError(f"{label} must use Decimal or a decimal string, not float")
    return value


class OrderCreationOutcome(StrEnum):
    CREATED = "CREATED"
    REJECTED = "REJECTED"


class OrderCreationRejectionReason(StrEnum):
    ELIGIBILITY_NOT_BEFORE_EXPIRY = "ELIGIBILITY_NOT_BEFORE_EXPIRY"
    QUANTITY_INCREMENT_MISMATCH = "QUANTITY_INCREMENT_MISMATCH"


class SimulatedOrderProjectionState(StrEnum):
    CREATED = "CREATED"
    ELIGIBLE = "ELIGIBLE"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    FILL_READY = "FILL_READY"
    EXPIRED_UNFILLED = "EXPIRED_UNFILLED"
    NO_ELIGIBLE_DATA = "NO_ELIGIBLE_DATA"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


_TERMINAL_STATES = {
    SimulatedOrderProjectionState.FILL_READY,
    SimulatedOrderProjectionState.EXPIRED_UNFILLED,
    SimulatedOrderProjectionState.NO_ELIGIBLE_DATA,
    SimulatedOrderProjectionState.CANCELLED,
    SimulatedOrderProjectionState.REJECTED,
}


class LiquidityResolutionOutcome(StrEnum):
    NOT_EVALUATED = "NOT_EVALUATED"
    FULL_FILL_AVAILABLE = "FULL_FILL_AVAILABLE"
    INSUFFICIENT_FOR_FULL_FILL = "INSUFFICIENT_FOR_FULL_FILL"


class OrderCreationCommand(BaseModel):
    """Idempotent request derived from one authoritative reserved proposal result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    command_id: OrderCreationCommandId
    schema_version: Literal["order-creation-command-v2"] = "order-creation-command-v2"
    artifact_id: ReplayArtifactId
    orchestration_result_id: OrchestrationResultId
    run_id: SimulationRunId
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    proposal_id: TradeProposalId
    strategy_decision_id: StrategyDecisionId
    risk_decision_id: RiskDecisionId
    reservation_id: ReservationId
    execution_model_id: SimulationExecutionModelId
    liquidity_model_id: SimulationLiquidityModelId
    schedule_id: ReplayScheduleId
    scheduler_position: int = Field(gt=0)
    created_at: datetime

    @classmethod
    def _issue(
        cls,
        result: CausalOrchestrationResult,
        execution_configuration: SimulationExecutionConfiguration,
        liquidity_configuration: SimulationLiquidityConfiguration,
        view: OrchestrationMarketView,
    ) -> OrderCreationCommand:
        if not isinstance(result.strategy_decision, TradeProposalDecision):
            raise ValueError("only a trade proposal can request simulated-order creation")
        attempt = result.risk_attempt
        if attempt is None or attempt.reservation is None:
            raise ValueError("simulated-order creation requires reservation evidence")
        content: dict[str, object] = {
            "schema_version": "order-creation-command-v2",
            "artifact_id": result.artifact_id,
            "orchestration_result_id": result.orchestration_result_id,
            "run_id": result.run_id,
            "account_id": result.account_id,
            "allocation_id": result.allocation_id,
            "agent_id": result.agent_id,
            "proposal_id": result.strategy_decision.proposal.proposal_id,
            "strategy_decision_id": result.strategy_decision.decision_id,
            "risk_decision_id": attempt.risk_decision.risk_decision_id,
            "reservation_id": attempt.reservation.reservation_id,
            "execution_model_id": execution_configuration.execution_model_id,
            "liquidity_model_id": liquidity_configuration.liquidity_model_id,
            "schedule_id": view.schedule.schedule_id,
            "scheduler_position": view.scheduler_position,
            "created_at": view.causal_at,
        }
        return cls.model_validate(
            {"command_id": calculate_order_creation_command_id(content), **content}
        )

    @field_validator("created_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.command_id != calculate_order_creation_command_id(self):
            raise ValueError("order creation command identity does not match content")
        return self


def calculate_order_creation_command_id(
    command: OrderCreationCommand | dict[str, object],
) -> OrderCreationCommandId:
    return OrderCreationCommandId.parse(sha256_content_id_v2(_without_id(command, "command_id")))


class OrderCancellationCommand(BaseModel):
    """Engine-stamped cancellation request bound to one authoritative cursor position."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cancellation_command_id: OrderCancellationCommandId
    schema_version: Literal["order-cancellation-command-v1"] = "order-cancellation-command-v1"
    run_id: SimulationRunId
    order_id: SimulatedOrderId
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    schedule_id: ReplayScheduleId
    scheduler_position: int = Field(gt=0)
    requested_at: datetime
    effective_at: datetime

    @field_validator("requested_at", "effective_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_command(self) -> Self:
        if self.effective_at < self.requested_at:
            raise ValueError("cancellation cannot become effective before it is requested")
        if self.cancellation_command_id != calculate_order_cancellation_command_id(self):
            raise ValueError("order cancellation command identity does not match content")
        return self


def calculate_order_cancellation_command_id(
    command: OrderCancellationCommand | dict[str, object],
) -> OrderCancellationCommandId:
    return OrderCancellationCommandId.parse(
        sha256_content_id_v2(_without_id(command, "cancellation_command_id"))
    )


class OrderTerminalResolution(BaseModel):
    """Immutable terminal decision over one order and one exact released market prefix."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    terminal_resolution_id: OrderTerminalResolutionId
    schema_version: Literal["order-terminal-resolution-v1"] = "order-terminal-resolution-v1"
    creation_command_id: OrderCreationCommandId
    orchestration_result_id: OrchestrationResultId
    artifact_id: ReplayArtifactId
    run_id: SimulationRunId
    order_id: SimulatedOrderId
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    proposal_id: TradeProposalId
    risk_decision_id: RiskDecisionId
    reservation_id: ReservationId
    execution_model_id: SimulationExecutionModelId
    liquidity_model_id: SimulationLiquidityModelId
    schedule_id: ReplayScheduleId
    scheduler_position: int = Field(gt=0)
    released_market_event_ids: tuple[MarketEventId, ...]
    candidate_market_event_ids: tuple[MarketEventId, ...]
    cancellation_command_id: OrderCancellationCommandId | None = None
    liquidity_outcome: LiquidityResolutionOutcome
    maximum_fill_quantity: Annotated[Decimal | None, Field(ge=0, allow_inf_nan=False)] = None
    payload: ExecutionResolutionPayload

    @field_validator("maximum_fill_quantity", mode="before")
    @classmethod
    def reject_float_quantity(cls, value: object) -> object:
        return _reject_float(value, "maximum fill quantity")

    @model_validator(mode="after")
    def validate_resolution(self) -> Self:
        if len(set(self.released_market_event_ids)) != len(self.released_market_event_ids):
            raise ValueError("released resolution market evidence contains duplicates")
        if len(set(self.candidate_market_event_ids)) != len(self.candidate_market_event_ids):
            raise ValueError("candidate resolution market evidence contains duplicates")
        if not set(self.candidate_market_event_ids).issubset(self.released_market_event_ids):
            raise ValueError("execution candidates must belong to the released market prefix")
        if self.payload.run_id != self.run_id or self.payload.order_id != self.order_id:
            raise ValueError("terminal payload attribution differs from order resolution")
        source_id = self.payload.source_market_event_id
        if source_id is not None and source_id not in self.candidate_market_event_ids:
            raise ValueError("terminal source event is not an authoritative candidate")
        has_liquidity_source = (
            self.liquidity_outcome is not LiquidityResolutionOutcome.NOT_EVALUATED
        )
        if has_liquidity_source != (self.maximum_fill_quantity is not None):
            raise ValueError("liquidity evidence and maximum fill quantity are inconsistent")
        if self.liquidity_outcome is LiquidityResolutionOutcome.INSUFFICIENT_FOR_FULL_FILL and (
            self.payload.outcome is not ExecutionResolutionOutcome.REJECTED
            or self.payload.reason is not ExecutionResolutionReason.INSUFFICIENT_LIQUIDITY
        ):
            raise ValueError("insufficient liquidity must produce a typed rejection")
        if self.liquidity_outcome is LiquidityResolutionOutcome.FULL_FILL_AVAILABLE and (
            self.payload.outcome is not ExecutionResolutionOutcome.FILL_READY
        ):
            raise ValueError("available full-fill liquidity must produce fill-ready evidence")
        if (
            self.payload.outcome
            not in {ExecutionResolutionOutcome.FILL_READY, ExecutionResolutionOutcome.REJECTED}
            and self.liquidity_outcome is not LiquidityResolutionOutcome.NOT_EVALUATED
        ):
            raise ValueError("non-execution terminal evidence cannot claim liquidity evaluation")
        if self.payload.outcome is ExecutionResolutionOutcome.CANCELLED and (
            self.cancellation_command_id is None
        ):
            raise ValueError("cancelled evidence requires its authoritative cancellation command")
        if self.terminal_resolution_id != calculate_order_terminal_resolution_id(self):
            raise ValueError("terminal order resolution identity does not match content")
        return self


def calculate_order_terminal_resolution_id(
    resolution: OrderTerminalResolution | dict[str, object],
) -> OrderTerminalResolutionId:
    return OrderTerminalResolutionId.parse(
        sha256_content_id_v2(_without_id(resolution, "terminal_resolution_id"))
    )


class SimulatedOrderProjection(BaseModel):
    """Versioned in-memory projection; it has no accounting mutation authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    projection_id: OrderProjectionId
    schema_version: Literal["simulated-order-projection-v1"] = "simulated-order-projection-v1"
    revision: int = Field(gt=0)
    creation_command_id: OrderCreationCommandId
    order: SimulatedOrder
    state: SimulatedOrderProjectionState
    cancellation: OrderCancellationCommand | None = None
    terminal_resolution: OrderTerminalResolution | None = None

    @model_validator(mode="after")
    def validate_projection(self) -> Self:
        is_terminal = self.state in _TERMINAL_STATES
        if is_terminal != (self.terminal_resolution is not None):
            raise ValueError("terminal projection state and resolution evidence differ")
        if (
            self.state is SimulatedOrderProjectionState.CANCEL_REQUESTED
            and self.cancellation is None
        ):
            raise ValueError("cancel-requested projection requires its command")
        if self.cancellation is not None and self.cancellation.order_id != self.order.order_id:
            raise ValueError("cancellation command belongs to a different order")
        if self.cancellation is not None and (
            self.cancellation.run_id != self.order.run_id
            or self.cancellation.account_id != self.order.account_id
            or self.cancellation.allocation_id != self.order.allocation_id
            or self.cancellation.agent_id != self.order.agent_id
        ):
            raise ValueError("cancellation attribution differs from its order")
        if self.terminal_resolution is not None and (
            self.terminal_resolution.order_id != self.order.order_id
            or self.terminal_resolution.creation_command_id != self.creation_command_id
        ):
            raise ValueError("terminal resolution belongs to a different order projection")
        if self.terminal_resolution is not None:
            terminal = self.terminal_resolution
            if (
                terminal.run_id != self.order.run_id
                or terminal.account_id != self.order.account_id
                or terminal.allocation_id != self.order.allocation_id
                or terminal.agent_id != self.order.agent_id
                or terminal.proposal_id != self.order.proposal_id
                or terminal.risk_decision_id != self.order.risk_decision_id
                or terminal.reservation_id != self.order.reservation_id
                or terminal.execution_model_id != self.order.execution_model_id
                or terminal.cancellation_command_id
                != (
                    self.cancellation.cancellation_command_id
                    if self.cancellation is not None
                    and terminal.payload.outcome is ExecutionResolutionOutcome.CANCELLED
                    else None
                )
                or self.state != _projection_state_for(terminal.payload.outcome)
            ):
                raise ValueError("terminal attribution differs from authoritative order evidence")
        if self.projection_id != calculate_order_projection_id(self):
            raise ValueError("simulated-order projection identity does not match content")
        return self


def calculate_order_projection_id(
    projection: SimulatedOrderProjection | dict[str, object],
) -> OrderProjectionId:
    return OrderProjectionId.parse(sha256_content_id_v2(_without_id(projection, "projection_id")))


class OrderCreationReceipt(BaseModel):
    """Content-identified idempotent order-creation outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    receipt_id: OrderCreationReceiptId
    schema_version: Literal["order-creation-receipt-v1"] = "order-creation-receipt-v1"
    command_id: OrderCreationCommandId
    orchestration_result_id: OrchestrationResultId
    outcome: OrderCreationOutcome
    rejection_reason: OrderCreationRejectionReason | None = None
    order_id: SimulatedOrderId | None = None
    projection_id: OrderProjectionId | None = None

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        created = self.outcome is OrderCreationOutcome.CREATED
        if created != (self.order_id is not None and self.projection_id is not None):
            raise ValueError("created order receipt must identify its order projection")
        if created == (self.rejection_reason is not None):
            raise ValueError("order creation outcome and rejection reason are inconsistent")
        if self.receipt_id != calculate_order_creation_receipt_id(self):
            raise ValueError("order creation receipt identity does not match content")
        return self


def calculate_order_creation_receipt_id(
    receipt: OrderCreationReceipt | dict[str, object],
) -> OrderCreationReceiptId:
    return OrderCreationReceiptId.parse(sha256_content_id_v2(_without_id(receipt, "receipt_id")))


class OrderResolutionInvariantError(ValueError):
    """Raised when order evidence is foreign, forged, or not causally resolvable."""


class OrderProjectionNotFoundError(KeyError):
    """Raised when an order is outside this resolver's isolated run scope."""


@dataclass(frozen=True, slots=True)
class _OrderResolverState:
    """Single publication root for exception-atomic in-memory resolver state."""

    receipts: Mapping[OrderCreationCommandId, OrderCreationReceipt]
    projections: Mapping[SimulatedOrderId, SimulatedOrderProjection]
    source_results: Mapping[SimulatedOrderId, CausalOrchestrationResult]
    cancellations: Mapping[SimulatedOrderId, OrderCancellationCommand]


class OrderTerminalResolver:
    """Process-local idempotent projection owner over pure deterministic resolution."""

    def __init__(
        self,
        *,
        artifact: ReplayArtifactBundle,
        dataset: CanonicalDataset,
        orchestrator: CausalOrchestrator,
        execution_configuration: SimulationExecutionConfiguration,
        liquidity_configuration: SimulationLiquidityConfiguration,
        failure_injector: Callable[[str], None] | None = None,
    ) -> None:
        self._artifact = ReplayArtifactBundle.model_validate(artifact.model_dump(mode="python"))
        self._dataset = CanonicalDataset.model_validate(dataset.model_dump(mode="python"))
        self._execution_configuration = SimulationExecutionConfiguration.model_validate(
            execution_configuration.model_dump(mode="python")
        )
        self._liquidity_configuration = SimulationLiquidityConfiguration.model_validate(
            liquidity_configuration.model_dump(mode="python")
        )
        self._orchestrator = orchestrator
        self._failure_injector = failure_injector
        self._lock = Lock()
        self._state = _OrderResolverState({}, {}, {}, {})
        manifest = self._artifact.manifest
        if self._dataset.dataset_id != manifest.dataset_id:
            raise OrderResolutionInvariantError("resolver dataset differs from run manifest")
        if self._execution_configuration.execution_model_id != manifest.execution_model_id:
            raise OrderResolutionInvariantError(
                "resolver execution model differs from run manifest"
            )
        if manifest.schema_version != "simulation-run-manifest-v2":
            raise OrderResolutionInvariantError(
                "Phase 6.1 resolution requires a V2 manifest with frozen liquidity"
            )
        if manifest.liquidity_configuration != self._liquidity_configuration:
            raise OrderResolutionInvariantError(
                "resolver liquidity configuration differs from run manifest"
            )
        if orchestrator.scheduler.schedule != self._schedule:
            raise OrderResolutionInvariantError(
                "resolver orchestrator schedule differs from artifact"
            )
        self._bars_by_reference = self._resolve_market_registry()

    @property
    def _schedule(self) -> ReplaySchedule:
        return ReplaySchedule.from_artifact(self._artifact)

    def _inject(self, stage: str) -> None:
        if self._failure_injector is not None:
            self._failure_injector(stage)

    def issue_creation_command(self, result: CausalOrchestrationResult) -> OrderCreationCommand:
        """Issue a command only at the exact committed orchestration cursor."""
        with self._lock:
            authoritative = self._orchestrator.validate_result(result)
            view = self._orchestrator.market_view()
            self._validate_creation_view(authoritative, view)
            return OrderCreationCommand._issue(
                authoritative,
                self._execution_configuration,
                self._liquidity_configuration,
                view,
            )

    def create_order(
        self,
        command: OrderCreationCommand,
        result: CausalOrchestrationResult,
    ) -> OrderCreationReceipt:
        """Create one deterministic order or return the prior idempotent receipt."""
        with self._lock:
            self._inject("before_authoritative_result_validation")
            authoritative = self._orchestrator.validate_result(result)
            self._validate_creation_command(command, authoritative)
            self._inject("after_authoritative_result_validation")
            prior = self._state.receipts.get(command.command_id)
            if prior is not None:
                self._validate_receipt_state(prior)
                return prior
            view = self._orchestrator.market_view()
            self._validate_creation_view(authoritative, view, command)
            built = self._build_creation(command, authoritative)
            self._inject("before_order_creation_commit")
            receipt, projection = built
            receipts = dict(self._state.receipts)
            projections = dict(self._state.projections)
            sources = dict(self._state.source_results)
            receipts[command.command_id] = receipt
            self._inject("after_creation_receipt_staged")
            if projection is not None:
                projections[projection.order.order_id] = projection
                self._inject("after_creation_projection_staged")
                sources[projection.order.order_id] = authoritative
                self._inject("after_creation_source_result_staged")
            self._publish_state(
                _OrderResolverState(receipts, projections, sources, self._state.cancellations),
                "order_creation",
            )
            return receipt

    def projection(self, order_id: SimulatedOrderId) -> SimulatedOrderProjection:
        with self._lock:
            try:
                return self._state.projections[order_id]
            except KeyError as exc:
                raise OrderProjectionNotFoundError(str(order_id)) from exc

    def request_cancellation(
        self,
        order_id: SimulatedOrderId,
        *,
        expected_scheduler_position: int,
    ) -> OrderCancellationCommand:
        """Stamp a cancellation request from the current authoritative cursor view."""
        with self._lock:
            projection = self._get_projection(order_id)
            prior = self._state.cancellations.get(order_id)
            if prior is not None:
                return prior
            view = self._orchestrator.market_view()
            if view.causal_at is None:
                raise OrderResolutionInvariantError("cancellation requires a consumed causal event")
            if expected_scheduler_position != view.scheduler_position:
                raise OrderResolutionInvariantError(
                    "cancellation cursor changed before authoritative publication"
                )
            content: dict[str, object] = {
                "schema_version": "order-cancellation-command-v1",
                "run_id": projection.order.run_id,
                "order_id": order_id,
                "account_id": projection.order.account_id,
                "allocation_id": projection.order.allocation_id,
                "agent_id": projection.order.agent_id,
                "schedule_id": view.schedule.schedule_id,
                "scheduler_position": view.scheduler_position,
                "requested_at": view.causal_at,
                "effective_at": view.causal_at,
            }
            cancellation = OrderCancellationCommand.model_validate(
                {
                    "cancellation_command_id": calculate_order_cancellation_command_id(content),
                    **content,
                }
            )
            if projection.terminal_resolution is not None:
                if projection.terminal_resolution.payload.resolved_at > cancellation.effective_at:
                    raise OrderResolutionInvariantError(
                        "cancellation cannot precede already-published future terminal evidence"
                    )
                updated = self._projection(
                    projection,
                    revision=projection.revision + 1,
                    cancellation=cancellation,
                )
            else:
                updated = self._projection(
                    projection,
                    revision=projection.revision + 1,
                    state=SimulatedOrderProjectionState.CANCEL_REQUESTED,
                    cancellation=cancellation,
                )
            self._inject("before_cancellation_commit")
            cancellations = dict(self._state.cancellations)
            projections = dict(self._state.projections)
            cancellations[order_id] = cancellation
            self._inject("after_cancellation_command_staged")
            projections[order_id] = updated
            self._inject("after_cancellation_projection_staged")
            self._publish_state(
                _OrderResolverState(
                    self._state.receipts,
                    projections,
                    self._state.source_results,
                    cancellations,
                ),
                "cancellation",
            )
            return cancellation

    def resolve(self, order_id: SimulatedOrderId) -> SimulatedOrderProjection:
        """Resolve using only the exact market prefix currently released by orchestration."""
        with self._lock:
            projection = self._get_projection(order_id)
            if projection.state in _TERMINAL_STATES:
                return projection
            view = self._orchestrator.market_view()
            if view.schedule.schedule_id != self._schedule.schedule_id:
                raise OrderResolutionInvariantError("resolution view belongs to another schedule")
            source_result = self._state.source_results[order_id]
            self._orchestrator.validate_result(source_result)
            self._inject("before_terminal_resolution")
            terminal = self._resolve_terminal(projection, source_result, view)
            if terminal is None:
                if (
                    projection.state is SimulatedOrderProjectionState.CREATED
                    and view.causal_at is not None
                    and view.causal_at >= projection.order.eligible_at
                ):
                    updated = self._projection(
                        projection,
                        revision=projection.revision + 1,
                        state=SimulatedOrderProjectionState.ELIGIBLE,
                    )
                    self._inject("before_eligibility_commit")
                    projections = dict(self._state.projections)
                    projections[order_id] = updated
                    self._publish_state(
                        _OrderResolverState(
                            self._state.receipts,
                            projections,
                            self._state.source_results,
                            self._state.cancellations,
                        ),
                        "eligibility",
                    )
                    return updated
                return projection
            state = _projection_state_for(terminal.payload.outcome)
            updated = self._projection(
                projection,
                revision=projection.revision + 1,
                state=state,
                terminal_resolution=terminal,
            )
            self._validate_terminal_context(updated, source_result)
            self._inject("before_terminal_commit")
            projections = dict(self._state.projections)
            projections[order_id] = updated
            self._publish_state(
                _OrderResolverState(
                    self._state.receipts,
                    projections,
                    self._state.source_results,
                    self._state.cancellations,
                ),
                "terminal",
            )
            return updated

    def validate_terminal_resolution(self, value: object) -> OrderTerminalResolution:
        """Validate terminal evidence against this resolver's committed authority."""
        candidate = OrderTerminalResolution.model_validate(value)
        with self._lock:
            projection = self._get_projection(candidate.order_id)
            authoritative = projection.terminal_resolution
            if authoritative is None or candidate != authoritative:
                raise OrderResolutionInvariantError(
                    "terminal evidence was not issued by this resolver"
                )
            source = self._state.source_results[candidate.order_id]
            self._validate_terminal_context(projection, source)
            return authoritative

    def validate_projection(self, value: object) -> SimulatedOrderProjection:
        """Validate projection evidence against the resolver-owned publication root."""
        candidate = SimulatedOrderProjection.model_validate(value)
        with self._lock:
            authoritative = self._get_projection(candidate.order.order_id)
            if candidate != authoritative:
                raise OrderResolutionInvariantError(
                    "projection evidence was not issued by this resolver"
                )
            if authoritative.terminal_resolution is not None:
                self._validate_terminal_context(
                    authoritative,
                    self._state.source_results[authoritative.order.order_id],
                )
            return authoritative

    def _resolve_terminal(
        self,
        projection: SimulatedOrderProjection,
        result: CausalOrchestrationResult,
        view: OrchestrationMarketView,
    ) -> OrderTerminalResolution | None:
        order = projection.order
        session = self._proposal_session(result)
        effective_expiry = min(order.valid_until, session.close_at)
        released = view.released_market_events
        released_ids = tuple(item.market_event_id for item in released)
        candidates = self._eligible_released_candidates(order, session.session_id, released)
        candidate_ids = tuple(reference.market_event_id for reference, _ in candidates)
        cancellation = projection.cancellation
        selected = candidates[0] if candidates else None
        if selected is not None:
            reference, bar = selected
            if cancellation is not None and cancellation.effective_at < bar.start_at:
                return self._terminal(
                    projection,
                    result,
                    view,
                    released_ids,
                    candidate_ids,
                    ExecutionResolutionOutcome.CANCELLED,
                    ExecutionResolutionReason.CANCELLATION_EFFECTIVE,
                    cancellation.effective_at,
                    None,
                    LiquidityResolutionOutcome.NOT_EVALUATED,
                    None,
                )
            with localcontext(Context(prec=34)):
                maximum = (
                    bar.volume * self._liquidity_configuration.maximum_bar_volume_participation
                )
            if order.quantity > maximum:
                return self._terminal(
                    projection,
                    result,
                    view,
                    released_ids,
                    candidate_ids,
                    ExecutionResolutionOutcome.REJECTED,
                    ExecutionResolutionReason.INSUFFICIENT_LIQUIDITY,
                    reference.available_at,
                    reference.market_event_id,
                    LiquidityResolutionOutcome.INSUFFICIENT_FOR_FULL_FILL,
                    maximum,
                )
            return self._terminal(
                projection,
                result,
                view,
                released_ids,
                candidate_ids,
                ExecutionResolutionOutcome.FILL_READY,
                None,
                reference.available_at,
                reference.market_event_id,
                LiquidityResolutionOutcome.FULL_FILL_AVAILABLE,
                maximum,
            )
        causal_at = view.causal_at
        if (
            cancellation is not None
            and causal_at is not None
            and causal_at >= cancellation.effective_at
            and cancellation.effective_at <= order.eligible_at
        ):
            return self._terminal(
                projection,
                result,
                view,
                released_ids,
                candidate_ids,
                ExecutionResolutionOutcome.CANCELLED,
                ExecutionResolutionReason.CANCELLATION_EFFECTIVE,
                cancellation.effective_at,
                None,
                LiquidityResolutionOutcome.NOT_EVALUATED,
                None,
            )
        if not view.exhausted:
            return None
        if cancellation is not None and cancellation.effective_at < effective_expiry:
            return self._terminal(
                projection,
                result,
                view,
                released_ids,
                candidate_ids,
                ExecutionResolutionOutcome.CANCELLED,
                ExecutionResolutionReason.CANCELLATION_EFFECTIVE,
                cancellation.effective_at,
                None,
                LiquidityResolutionOutcome.NOT_EVALUATED,
                None,
            )
        if causal_at is None:
            raise OrderResolutionInvariantError(
                "terminal resolution requires an authoritative causal clock"
            )
        if causal_at >= order.valid_until and order.valid_until <= session.close_at:
            return self._terminal(
                projection,
                result,
                view,
                released_ids,
                candidate_ids,
                ExecutionResolutionOutcome.EXPIRED_UNFILLED,
                ExecutionResolutionReason.ORDER_VALIDITY_EXPIRED,
                causal_at,
                None,
                LiquidityResolutionOutcome.NOT_EVALUATED,
                None,
            )
        reason = (
            ExecutionResolutionReason.NO_ELIGIBLE_SAME_SESSION_BAR
            if causal_at >= session.close_at
            else ExecutionResolutionReason.END_OF_DATA_BEFORE_EXPIRY
        )
        return self._terminal(
            projection,
            result,
            view,
            released_ids,
            candidate_ids,
            ExecutionResolutionOutcome.NO_ELIGIBLE_DATA,
            reason,
            causal_at,
            None,
            LiquidityResolutionOutcome.NOT_EVALUATED,
            None,
        )

    def _terminal(
        self,
        projection: SimulatedOrderProjection,
        result: CausalOrchestrationResult,
        view: OrchestrationMarketView,
        released_ids: tuple[MarketEventId, ...],
        candidate_ids: tuple[MarketEventId, ...],
        outcome: ExecutionResolutionOutcome,
        reason: ExecutionResolutionReason | None,
        resolved_at: datetime,
        source_market_event_id: MarketEventId | None,
        liquidity_outcome: LiquidityResolutionOutcome,
        maximum_fill_quantity: Decimal | None,
    ) -> OrderTerminalResolution:
        order = projection.order
        if view.causal_at is None or resolved_at > view.causal_at:
            raise OrderResolutionInvariantError(
                "terminal evidence cannot be dated after the authoritative causal clock"
            )
        extended_v3 = (
            outcome is ExecutionResolutionOutcome.CANCELLED
            or reason is ExecutionResolutionReason.END_OF_DATA_BEFORE_EXPIRY
            or (
                outcome is ExecutionResolutionOutcome.REJECTED
                and reason is ExecutionResolutionReason.INSUFFICIENT_LIQUIDITY
            )
        )
        payload_content: dict[str, object] = {
            "schema_version": (
                "execution-resolution-payload-v3"
                if extended_v3
                else "execution-resolution-payload-v2"
            ),
            "run_id": order.run_id,
            "order_id": order.order_id,
            "resolved_at": resolved_at,
            "outcome": outcome,
            "reason": reason,
            "source_market_event_id": source_market_event_id,
        }
        payload = ExecutionResolutionPayload.model_validate(
            {"payload_id": calculate_marker_payload_id(payload_content), **payload_content}
        )
        content: dict[str, object] = {
            "schema_version": "order-terminal-resolution-v1",
            "creation_command_id": projection.creation_command_id,
            "orchestration_result_id": result.orchestration_result_id,
            "artifact_id": result.artifact_id,
            "run_id": order.run_id,
            "order_id": order.order_id,
            "account_id": order.account_id,
            "allocation_id": order.allocation_id,
            "agent_id": order.agent_id,
            "proposal_id": order.proposal_id,
            "risk_decision_id": order.risk_decision_id,
            "reservation_id": order.reservation_id,
            "execution_model_id": order.execution_model_id,
            "liquidity_model_id": self._liquidity_configuration.liquidity_model_id,
            "schedule_id": view.schedule.schedule_id,
            "scheduler_position": view.scheduler_position,
            "released_market_event_ids": released_ids,
            "candidate_market_event_ids": candidate_ids,
            "cancellation_command_id": (
                projection.cancellation.cancellation_command_id
                if projection.cancellation is not None
                and outcome is ExecutionResolutionOutcome.CANCELLED
                else None
            ),
            "liquidity_outcome": liquidity_outcome,
            "maximum_fill_quantity": maximum_fill_quantity,
            "payload": payload,
        }
        return OrderTerminalResolution.model_validate(
            {
                "terminal_resolution_id": calculate_order_terminal_resolution_id(content),
                **content,
            }
        )

    def _build_creation(
        self,
        command: OrderCreationCommand,
        result: CausalOrchestrationResult,
    ) -> tuple[OrderCreationReceipt, SimulatedOrderProjection | None]:
        assert isinstance(result.strategy_decision, TradeProposalDecision)
        assert result.risk_attempt is not None
        assert result.risk_attempt.reservation is not None
        sizing = result.risk_attempt.risk_decision.sizing_decision
        assert sizing is not None
        proposal = result.strategy_decision.proposal
        with localcontext(Context(prec=34)):
            aligned = sizing.quantity % self._execution_configuration.quantity_increment == 0
        if not aligned:
            return self._rejected_receipt(
                command, OrderCreationRejectionReason.QUANTITY_INCREMENT_MISMATCH
            )
        submitted_at = command.created_at
        eligible_at = submitted_at + timedelta(
            seconds=self._execution_configuration.routing_latency_seconds
        )
        valid_until = min(proposal.valid_until, result.risk_attempt.reservation.expires_at)
        if eligible_at >= valid_until:
            return self._rejected_receipt(
                command, OrderCreationRejectionReason.ELIGIBILITY_NOT_BEFORE_EXPIRY
            )
        order_content: dict[str, object] = {
            "schema_version": "simulated-order-v1",
            "run_id": result.run_id,
            "account_id": result.account_id,
            "allocation_id": result.allocation_id,
            "agent_id": result.agent_id,
            "strategy_id": result.strategy_id,
            "management_mandate_id": proposal.management_mandate.mandate_id,
            "proposal_id": proposal.proposal_id,
            "strategy_decision_id": result.strategy_decision.decision_id,
            "risk_decision_id": result.risk_attempt.risk_decision.risk_decision_id,
            "reservation_id": result.risk_attempt.reservation.reservation_id,
            "instrument_id": proposal.instrument_id,
            "side": SimulatedOrderSide.BUY,
            "order_type": SimulatedOrderType.MARKET,
            "quantity": sizing.quantity,
            "currency": sizing.currency,
            "execution_model_id": self._execution_configuration.execution_model_id,
            "decision_at": proposal.as_of,
            "submitted_at": submitted_at,
            "eligible_at": eligible_at,
            "valid_until": valid_until,
        }
        order = SimulatedOrder.model_validate(
            {"order_id": calculate_simulated_order_id(order_content), **order_content}
        )
        projection_content: dict[str, object] = {
            "schema_version": "simulated-order-projection-v1",
            "revision": 1,
            "creation_command_id": command.command_id,
            "order": order,
            "state": SimulatedOrderProjectionState.CREATED,
            "cancellation": None,
            "terminal_resolution": None,
        }
        projection = SimulatedOrderProjection.model_validate(
            {
                "projection_id": calculate_order_projection_id(projection_content),
                **projection_content,
            }
        )
        receipt_content: dict[str, object] = {
            "schema_version": "order-creation-receipt-v1",
            "command_id": command.command_id,
            "orchestration_result_id": result.orchestration_result_id,
            "outcome": OrderCreationOutcome.CREATED,
            "rejection_reason": None,
            "order_id": order.order_id,
            "projection_id": projection.projection_id,
        }
        receipt = OrderCreationReceipt.model_validate(
            {
                "receipt_id": calculate_order_creation_receipt_id(receipt_content),
                **receipt_content,
            }
        )
        return receipt, projection

    def _rejected_receipt(
        self,
        command: OrderCreationCommand,
        reason: OrderCreationRejectionReason,
    ) -> tuple[OrderCreationReceipt, None]:
        content: dict[str, object] = {
            "schema_version": "order-creation-receipt-v1",
            "command_id": command.command_id,
            "orchestration_result_id": command.orchestration_result_id,
            "outcome": OrderCreationOutcome.REJECTED,
            "rejection_reason": reason,
            "order_id": None,
            "projection_id": None,
        }
        return (
            OrderCreationReceipt.model_validate(
                {"receipt_id": calculate_order_creation_receipt_id(content), **content}
            ),
            None,
        )

    def _validate_creation_command(
        self,
        command: OrderCreationCommand,
        result: CausalOrchestrationResult,
    ) -> None:
        if result.outcome is not OrchestrationOutcome.CAPITAL_RESERVED:
            raise OrderResolutionInvariantError(
                "order creation requires an authoritative CAPITAL_RESERVED result"
            )
        if not isinstance(result.strategy_decision, TradeProposalDecision):
            raise OrderResolutionInvariantError("order creation requires a trade proposal")
        attempt = result.risk_attempt
        if (
            attempt is None
            or attempt.status is not ReservationAttemptStatus.RESERVED
            or attempt.reservation is None
            or attempt.risk_decision.sizing_decision is None
        ):
            raise OrderResolutionInvariantError(
                "order creation requires exact reservation evidence"
            )
        proposal = result.strategy_decision.proposal
        expected = (
            command.artifact_id == self._artifact.artifact_id == result.artifact_id
            and command.orchestration_result_id == result.orchestration_result_id
            and command.run_id == self._artifact.manifest.run_id == result.run_id
            and command.account_id == result.account_id
            and command.allocation_id == result.allocation_id
            and command.agent_id == result.agent_id
            and command.proposal_id == proposal.proposal_id
            and command.strategy_decision_id == result.strategy_decision.decision_id
            and command.risk_decision_id == attempt.risk_decision.risk_decision_id
            and command.reservation_id == attempt.reservation.reservation_id
            and command.execution_model_id == self._execution_configuration.execution_model_id
            and command.liquidity_model_id == self._liquidity_configuration.liquidity_model_id
            and command.schedule_id == self._schedule.schedule_id == result.schedule_id
            and command.scheduler_position == result.scheduler_position_after
            and command.created_at == result.evaluated_at
        )
        if not expected:
            raise OrderResolutionInvariantError(
                "order creation command differs from authoritative proposal/reservation context"
            )
        dimensions = result.execution_dimensions
        if (
            dimensions.execution_environment is not ExecutionEnvironment.SIMULATION
            or dimensions.submission_mode is not SubmissionMode.ORDER_ENABLED
        ):
            raise OrderResolutionInvariantError(
                "order creation requires SIMULATION with ORDER_ENABLED authority"
            )

    def _validate_creation_view(
        self,
        result: CausalOrchestrationResult,
        view: OrchestrationMarketView,
        command: OrderCreationCommand | None = None,
    ) -> None:
        if view.schedule.schedule_id != result.schedule_id:
            raise OrderResolutionInvariantError("order creation belongs to another schedule")
        if (
            view.scheduler_position != result.scheduler_position_after
            or view.causal_at != result.evaluated_at
        ):
            raise OrderResolutionInvariantError(
                "order creation cursor is stale or execution evidence is already available"
            )
        if command is not None and (
            command.schedule_id != view.schedule.schedule_id
            or command.scheduler_position != view.scheduler_position
            or command.created_at != view.causal_at
        ):
            raise OrderResolutionInvariantError(
                "order creation command differs from the authoritative causal cursor"
            )
        assert isinstance(result.strategy_decision, TradeProposalDecision)
        assert result.risk_attempt is not None
        assert result.risk_attempt.reservation is not None
        expires_at = min(
            result.strategy_decision.proposal.valid_until,
            result.risk_attempt.reservation.expires_at,
        )
        if view.causal_at is None or view.causal_at >= expires_at:
            raise OrderResolutionInvariantError("proposal or reservation is expired")

    def _validate_receipt_state(self, receipt: OrderCreationReceipt) -> None:
        if receipt.outcome is OrderCreationOutcome.REJECTED:
            return
        assert receipt.order_id is not None
        assert receipt.projection_id is not None
        projection = self._state.projections.get(receipt.order_id)
        if (
            projection is None
            or projection.projection_id != receipt.projection_id
            or receipt.order_id not in self._state.source_results
        ):
            raise OrderResolutionInvariantError(
                "creation receipt has no complete authoritative projection publication"
            )

    def _validate_terminal_context(
        self,
        projection: SimulatedOrderProjection,
        result: CausalOrchestrationResult,
    ) -> None:
        terminal = projection.terminal_resolution
        if terminal is None:
            raise OrderResolutionInvariantError("terminal validation requires terminal evidence")
        order = projection.order
        cancellation = self._state.cancellations.get(order.order_id)
        manifest = self._artifact.manifest
        expected = (
            terminal.creation_command_id == projection.creation_command_id
            and terminal.orchestration_result_id == result.orchestration_result_id
            and terminal.artifact_id == self._artifact.artifact_id == result.artifact_id
            and terminal.run_id == manifest.run_id == order.run_id == result.run_id
            and terminal.account_id == manifest.account_id == order.account_id == result.account_id
            and terminal.allocation_id
            == manifest.allocation_id
            == order.allocation_id
            == result.allocation_id
            and terminal.agent_id == manifest.agent_id == order.agent_id == result.agent_id
            and terminal.proposal_id == order.proposal_id
            and terminal.risk_decision_id == order.risk_decision_id
            and terminal.reservation_id == order.reservation_id
            and terminal.execution_model_id
            == manifest.execution_model_id
            == order.execution_model_id
            and terminal.liquidity_model_id == self._liquidity_configuration.liquidity_model_id
            and terminal.schedule_id == self._schedule.schedule_id == result.schedule_id
            and terminal.cancellation_command_id
            == (
                cancellation.cancellation_command_id
                if cancellation is not None
                and terminal.payload.outcome is ExecutionResolutionOutcome.CANCELLED
                else None
            )
        )
        if not expected:
            raise OrderResolutionInvariantError(
                "terminal evidence differs from authoritative order/run evidence"
            )
        if terminal.scheduler_position > len(self._schedule.events):
            raise OrderResolutionInvariantError("terminal scheduler position is outside the run")
        prefix_event_ids = {
            str(event.payload_id) for event in self._schedule.events[: terminal.scheduler_position]
        }
        artifact_event_ids = {str(item.market_event_id) for item in self._artifact.market_events}
        authoritative_released = tuple(
            item.market_event_id
            for item in self._artifact.market_events
            if str(item.market_event_id) in prefix_event_ids & artifact_event_ids
        )
        if set(terminal.released_market_event_ids) != set(authoritative_released):
            raise OrderResolutionInvariantError(
                "terminal released prefix differs from authoritative schedule"
            )

    def _publish_state(self, next_state: _OrderResolverState, operation: str) -> None:
        """Atomically replace every resolver registry, rolling back injected failures."""
        previous = self._state
        self._inject(f"before_{operation}_state_publication")
        self._state = next_state
        try:
            self._inject(f"after_{operation}_state_publication")
        except BaseException:
            self._state = previous
            raise

    def _proposal_session(self, result: CausalOrchestrationResult) -> TradingSession:
        bars = result.market_data.bars
        if not bars:
            raise OrderResolutionInvariantError("proposal has no authoritative market session")
        latest = bars[-1]
        calendar = UsEquitiesCalendar()
        session = calendar.session_for_date(
            latest.start_at.astimezone(ZoneInfo(calendar.market_timezone)).date()
        )
        if (
            session is None
            or latest.session_id != session.session_id
            or not calendar.contains_interval(latest.start_at, latest.end_at)
        ):
            raise OrderResolutionInvariantError("proposal session differs from XNYS calendar")
        return session

    def _eligible_released_candidates(
        self,
        order: SimulatedOrder,
        session_id: str,
        released: tuple[MarketEventReference, ...],
    ) -> tuple[tuple[MarketEventReference, HistoricalBar], ...]:
        values: list[tuple[MarketEventReference, HistoricalBar]] = []
        for reference in released:
            bar = self._bars_by_reference.get(reference.market_event_id)
            if bar is None:
                raise OrderResolutionInvariantError(
                    "released market event has no canonical dataset record"
                )
            if (
                bar.instrument_id == order.instrument_id
                and bar.session_id == session_id
                and bar.start_at > order.eligible_at
                and bar.start_at < order.valid_until
            ):
                values.append((reference, bar))
        return tuple(
            sorted(
                values,
                key=lambda item: (
                    item[1].start_at,
                    item[1].end_at,
                    str(item[0].market_event_id),
                ),
            )
        )

    def _resolve_market_registry(self) -> dict[MarketEventId, HistoricalBar]:
        bars_by_key = {
            (
                bar.instrument_id,
                bar.start_at,
                bar.end_at,
                bar.available_at,
                bar.source_record_id,
            ): bar
            for bar in self._dataset.bars
        }
        result: dict[MarketEventId, HistoricalBar] = {}
        for reference in self._artifact.market_events:
            key = (
                reference.instrument_id,
                reference.interval_start_at,
                reference.event_at,
                reference.available_at,
                reference.source_record_id,
            )
            bar = bars_by_key.get(key)
            if bar is None:
                raise OrderResolutionInvariantError(
                    "artifact market reference is absent from the canonical dataset"
                )
            result[reference.market_event_id] = bar
        return result

    def _get_projection(self, order_id: SimulatedOrderId) -> SimulatedOrderProjection:
        try:
            return self._state.projections[order_id]
        except KeyError as exc:
            raise OrderProjectionNotFoundError(str(order_id)) from exc

    @staticmethod
    def _projection(
        previous: SimulatedOrderProjection,
        **changes: object,
    ) -> SimulatedOrderProjection:
        content = previous.model_dump(mode="python", exclude={"projection_id"})
        content.update(changes)
        return SimulatedOrderProjection.model_validate(
            {"projection_id": calculate_order_projection_id(content), **content}
        )


def _projection_state_for(
    outcome: ExecutionResolutionOutcome,
) -> SimulatedOrderProjectionState:
    return {
        ExecutionResolutionOutcome.FILL_READY: SimulatedOrderProjectionState.FILL_READY,
        ExecutionResolutionOutcome.EXPIRED_UNFILLED: (
            SimulatedOrderProjectionState.EXPIRED_UNFILLED
        ),
        ExecutionResolutionOutcome.NO_ELIGIBLE_DATA: (
            SimulatedOrderProjectionState.NO_ELIGIBLE_DATA
        ),
        ExecutionResolutionOutcome.CANCELLED: SimulatedOrderProjectionState.CANCELLED,
        ExecutionResolutionOutcome.REJECTED: SimulatedOrderProjectionState.REJECTED,
    }[outcome]


def serialize_order_terminal_resolution(resolution: OrderTerminalResolution) -> bytes:
    """Return canonical bytes for determinism and durable-journal integration later."""
    return canonical_json_bytes_v2(resolution)
