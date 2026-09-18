"""Typed immutable replay artifacts and coherent simulation results."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_trading_scanner.domain import (
    AgentId,
    DatasetId,
    InstrumentId,
    MarketEventId,
    PortfolioSnapshotId,
    RealizedTradeResultId,
    ReplayArtifactId,
    ReplayEventId,
    SimulatedFillId,
    SimulatedOrderId,
    SimulationResultId,
    SimulationRunId,
)
from ai_trading_scanner.domain.content_identity import sha256_content_id_v2
from ai_trading_scanner.indicators import IndicatorSeries
from ai_trading_scanner.risk import RiskDecision
from ai_trading_scanner.simulation.models import (
    MarketEventReference,
    ReplayEvent,
    ReplayPayloadKind,
    ReplayPhase,
    SimulatedFill,
    SimulatedOrder,
    SimulationResultStatus,
    SimulationRunManifest,
    calculate_replay_trace_hash,
    order_replay_events,
    validate_fill_against_order,
)
from ai_trading_scanner.simulation.portfolio import (
    PortfolioSnapshot,
    PositionChange,
    RealizedTradeResult,
    reconcile_complete_portfolio,
)
from ai_trading_scanner.strategies import NoTradeDecision, TradeProposalDecision


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _without_id(value: BaseModel | dict[str, object], field: str) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude={field})
    return {key: item for key, item in value.items() if key != field}


class ExecutionResolutionOutcome(StrEnum):
    FILL_READY = "FILL_READY"
    EXPIRED_UNFILLED = "EXPIRED_UNFILLED"
    NO_ELIGIBLE_DATA = "NO_ELIGIBLE_DATA"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class ExecutionResolutionReason(StrEnum):
    ORDER_VALIDITY_EXPIRED = "ORDER_VALIDITY_EXPIRED"
    NO_ELIGIBLE_SAME_SESSION_BAR = "NO_ELIGIBLE_SAME_SESSION_BAR"
    CANCELLATION_EFFECTIVE = "CANCELLATION_EFFECTIVE"
    INSUFFICIENT_LIQUIDITY = "INSUFFICIENT_LIQUIDITY"
    EXECUTION_POLICY_REJECTED = "EXECUTION_POLICY_REJECTED"


class ExecutionResolutionPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    payload_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schema_version: Literal[
        "execution-resolution-payload-v2", "execution-resolution-payload-v3"
    ] = "execution-resolution-payload-v2"
    run_id: SimulationRunId
    order_id: SimulatedOrderId
    resolved_at: datetime
    outcome: ExecutionResolutionOutcome
    reason: ExecutionResolutionReason | None = None
    source_market_event_id: MarketEventId | None = None

    @field_validator("resolved_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_payload(self) -> Self:
        extended_v3 = self.outcome is ExecutionResolutionOutcome.CANCELLED or (
            self.outcome is ExecutionResolutionOutcome.REJECTED
            and self.reason is ExecutionResolutionReason.INSUFFICIENT_LIQUIDITY
        )
        required_schema = (
            "execution-resolution-payload-v3" if extended_v3 else "execution-resolution-payload-v2"
        )
        if self.schema_version != required_schema:
            raise ValueError("execution resolution behavior requires its schema version")
        expected_reasons = {
            ExecutionResolutionOutcome.FILL_READY: None,
            ExecutionResolutionOutcome.EXPIRED_UNFILLED: (
                ExecutionResolutionReason.ORDER_VALIDITY_EXPIRED
            ),
            ExecutionResolutionOutcome.NO_ELIGIBLE_DATA: (
                ExecutionResolutionReason.NO_ELIGIBLE_SAME_SESSION_BAR
            ),
            ExecutionResolutionOutcome.CANCELLED: (
                ExecutionResolutionReason.CANCELLATION_EFFECTIVE
            ),
            ExecutionResolutionOutcome.REJECTED: (
                ExecutionResolutionReason.EXECUTION_POLICY_REJECTED,
                ExecutionResolutionReason.INSUFFICIENT_LIQUIDITY,
            ),
        }[self.outcome]
        if isinstance(expected_reasons, tuple):
            reason_matches = self.reason in expected_reasons
        else:
            reason_matches = self.reason is expected_reasons
        if not reason_matches:
            raise ValueError("execution resolution outcome and reason are inconsistent")
        source_required = self.outcome is ExecutionResolutionOutcome.FILL_READY or (
            self.outcome is ExecutionResolutionOutcome.REJECTED
            and self.reason is ExecutionResolutionReason.INSUFFICIENT_LIQUIDITY
        )
        if source_required != (self.source_market_event_id is not None):
            raise ValueError("execution resolution market-source evidence is inconsistent")
        if self.payload_id != calculate_marker_payload_id(self):
            raise ValueError("execution resolution payload identity does not match content")
        return self


class SessionControlPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    payload_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schema_version: Literal["session-control-payload-v1"] = "session-control-payload-v1"
    run_id: SimulationRunId
    effective_at: datetime
    action: str = Field(min_length=1, max_length=64)

    @field_validator("effective_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_payload(self) -> Self:
        if self.payload_id != calculate_marker_payload_id(self):
            raise ValueError("session-control payload identity does not match content")
        return self


class IndicatorUpdatePayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    payload_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schema_version: Literal["indicator-update-payload-v1"] = "indicator-update-payload-v1"
    run_id: SimulationRunId
    agent_id: AgentId
    instrument_id: InstrumentId
    dataset_id: DatasetId
    as_of: datetime
    series: tuple[IndicatorSeries, ...] = Field(min_length=1)

    @field_validator("as_of")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_payload(self) -> Self:
        configuration_ids = tuple(item.configuration_id for item in self.series)
        if len(set(configuration_ids)) != len(configuration_ids):
            raise ValueError("indicator update configurations must be unique")
        if tuple(sorted(configuration_ids, key=str)) != configuration_ids:
            raise ValueError("indicator update configurations must be canonically ordered")
        if any(
            item.dataset_id != self.dataset_id
            or item.as_of != self.as_of
            or any(point.instrument_id != self.instrument_id for point in item.points)
            for item in self.series
        ):
            raise ValueError("indicator update causal lineage differs")
        if self.payload_id != calculate_marker_payload_id(self):
            raise ValueError("indicator update payload identity does not match content")
        return self


class ResultFinalizationPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    payload_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schema_version: Literal["result-finalization-payload-v1"] = "result-finalization-payload-v1"
    run_id: SimulationRunId
    status: SimulationResultStatus
    final_portfolio_snapshot_id: PortfolioSnapshotId
    realized_trade_result_ids: tuple[RealizedTradeResultId, ...] = ()
    finalized_at: datetime

    @field_validator("finalized_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_payload(self) -> Self:
        if len(set(self.realized_trade_result_ids)) != len(self.realized_trade_result_ids):
            raise ValueError("finalization realized trades must be unique")
        if self.payload_id != calculate_marker_payload_id(self):
            raise ValueError("result finalization payload identity does not match content")
        return self


MarkerPayload = (
    ExecutionResolutionPayload
    | SessionControlPayload
    | IndicatorUpdatePayload
    | ResultFinalizationPayload
)


def calculate_marker_payload_id(payload: MarkerPayload | dict[str, object]) -> str:
    return sha256_content_id_v2(_without_id(payload, "payload_id"))


_ORDER_INSENSITIVE_REGISTRIES: dict[str, tuple[str, ReplayPayloadKind]] = {
    "execution_resolutions": ("payload_id", ReplayPayloadKind.EXECUTION_RESOLUTION),
    "session_controls": ("payload_id", ReplayPayloadKind.SESSION_CONTROL),
    "market_events": ("market_event_id", ReplayPayloadKind.MARKET_EVENT),
    "indicator_updates": ("payload_id", ReplayPayloadKind.INDICATOR_UPDATE),
    "strategy_decisions": ("decision_id", ReplayPayloadKind.STRATEGY_DECISION),
    "risk_decisions": ("risk_decision_id", ReplayPayloadKind.RISK_DECISION),
    "orders": ("order_id", ReplayPayloadKind.SIMULATED_ORDER),
    "fills": ("fill_id", ReplayPayloadKind.SIMULATED_FILL),
    "position_changes": ("position_change_id", ReplayPayloadKind.POSITION_CHANGE),
    "portfolio_snapshots": ("portfolio_snapshot_id", ReplayPayloadKind.PORTFOLIO_SNAPSHOT),
    "realized_trades": ("realized_trade_result_id", ReplayPayloadKind.REALIZED_TRADE),
}


def _registry_identity(value: object, identity_field: str) -> str:
    if isinstance(value, BaseModel):
        return str(getattr(value, identity_field))
    if isinstance(value, dict):
        return str(value[identity_field])
    raise TypeError("replay artifact registry values must be models or dictionaries")


def _canonical_registry(
    values: object,
    identity_field: str,
    payload_kind: ReplayPayloadKind,
    event_positions: dict[tuple[ReplayPayloadKind, str], int],
) -> tuple[object, ...]:
    items: tuple[object, ...] = tuple(cast(Iterable[object], values))
    return tuple(
        sorted(
            items,
            key=lambda value: (
                event_positions.get(
                    (payload_kind, _registry_identity(value, identity_field)), len(event_positions)
                ),
                _registry_identity(value, identity_field),
            ),
        )
    )


class _PayloadBinding(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    kind: ReplayPayloadKind
    payload_id: str
    causal_at: datetime
    phase: ReplayPhase


class ReplayArtifactBundle(BaseModel):
    """Complete typed registry for one internally coherent replay trace."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: ReplayArtifactId
    schema_version: Literal["replay-artifact-v2"] = "replay-artifact-v2"
    manifest: SimulationRunManifest
    events: tuple[ReplayEvent, ...] = Field(min_length=1)
    execution_resolutions: tuple[ExecutionResolutionPayload, ...] = ()
    session_controls: tuple[SessionControlPayload, ...] = ()
    market_events: tuple[MarketEventReference, ...] = ()
    indicator_updates: tuple[IndicatorUpdatePayload, ...] = ()
    strategy_decisions: tuple[NoTradeDecision | TradeProposalDecision, ...] = ()
    risk_decisions: tuple[RiskDecision, ...] = ()
    orders: tuple[SimulatedOrder, ...] = ()
    fills: tuple[SimulatedFill, ...] = ()
    position_changes: tuple[PositionChange, ...] = ()
    portfolio_snapshots: tuple[PortfolioSnapshot, ...] = Field(min_length=1)
    realized_trades: tuple[RealizedTradeResult, ...] = ()
    finalizations: tuple[ResultFinalizationPayload, ...] = Field(min_length=1, max_length=1)

    @classmethod
    def create(cls, **content: object) -> ReplayArtifactBundle:
        events: tuple[ReplayEvent, ...] = tuple(content["events"])  # type: ignore[arg-type]
        ordered_events = order_replay_events(events)
        content["events"] = ordered_events
        event_positions = {
            (event.payload_kind, event.payload_id): index
            for index, event in enumerate(ordered_events)
        }
        content.setdefault("schema_version", "replay-artifact-v2")
        for field_name in _ORDER_INSENSITIVE_REGISTRIES:
            content.setdefault(field_name, ())
        for field_name, (identity_field, payload_kind) in _ORDER_INSENSITIVE_REGISTRIES.items():
            content[field_name] = _canonical_registry(
                content[field_name], identity_field, payload_kind, event_positions
            )
        return cls.model_validate({"artifact_id": calculate_replay_artifact_id(content), **content})

    @model_validator(mode="after")
    def validate_bundle(self) -> Self:
        if self.events != order_replay_events(self.events):
            raise ValueError("replay artifact events are not canonically ordered")
        event_positions = {
            (event.payload_kind, event.payload_id): index for index, event in enumerate(self.events)
        }
        for field_name, (identity_field, payload_kind) in _ORDER_INSENSITIVE_REGISTRIES.items():
            values = getattr(self, field_name)
            if values != _canonical_registry(values, identity_field, payload_kind, event_positions):
                raise ValueError(
                    f"replay artifact {field_name} registry is not canonically ordered"
                )
        run_id = self.manifest.run_id
        bindings: list[_PayloadBinding] = []

        def add(
            kind: ReplayPayloadKind,
            payload_id: object,
            at: datetime,
            phase: ReplayPhase,
        ) -> None:
            bindings.append(
                _PayloadBinding(kind=kind, payload_id=str(payload_id), causal_at=at, phase=phase)
            )

        for control in self.session_controls:
            if control.run_id != run_id:
                raise ValueError("session control belongs to a foreign run")
            add(
                ReplayPayloadKind.SESSION_CONTROL,
                control.payload_id,
                control.effective_at,
                ReplayPhase.SESSION_CONTROL,
            )
        for market in self.market_events:
            if market.dataset_id != self.manifest.dataset_id:
                raise ValueError("market event belongs to a foreign dataset")
            add(
                ReplayPayloadKind.MARKET_EVENT,
                market.market_event_id,
                market.available_at,
                ReplayPhase.MARKET_DATA_AVAILABLE,
            )
        for indicator in self.indicator_updates:
            if (
                indicator.run_id != run_id
                or indicator.agent_id != self.manifest.agent_id
                or indicator.dataset_id != self.manifest.dataset_id
                or tuple(item.configuration_id for item in indicator.series)
                != self.manifest.indicator_configuration_ids
            ):
                raise ValueError("indicator update attribution differs from run manifest")
            add(
                ReplayPayloadKind.INDICATOR_UPDATE,
                indicator.payload_id,
                indicator.as_of,
                ReplayPhase.INDICATOR_UPDATE,
            )
        for decision in self.strategy_decisions:
            if (
                decision.agent_id != self.manifest.agent_id
                or decision.strategy_id != self.manifest.strategy_id
                or decision.strategy_configuration_id != self.manifest.strategy_configuration_id
                or decision.dataset_id != self.manifest.dataset_id
                or decision.indicator_configuration_ids != self.manifest.indicator_configuration_ids
            ):
                raise ValueError("strategy decision attribution differs from run manifest")
            add(
                ReplayPayloadKind.STRATEGY_DECISION,
                decision.decision_id,
                decision.as_of,
                ReplayPhase.STRATEGY_EVALUATION,
            )
        for risk in self.risk_decisions:
            if (
                risk.account_id != self.manifest.account_id
                or risk.allocation_id != self.manifest.allocation_id
                or risk.agent_id != self.manifest.agent_id
                or risk.risk_configuration_id != self.manifest.risk_configuration_id
            ):
                raise ValueError("risk decision attribution differs from run manifest")
            add(
                ReplayPayloadKind.RISK_DECISION,
                risk.risk_decision_id,
                risk.evaluated_at,
                ReplayPhase.RISK_EVALUATION,
            )
        for order in self.orders:
            self._require_run_ownership(order)
            add(
                ReplayPayloadKind.SIMULATED_ORDER,
                order.order_id,
                order.submitted_at,
                ReplayPhase.ORDER_SUBMISSION,
            )
        order_by_id = {item.order_id: item for item in self.orders}
        market_by_id = {item.market_event_id: item for item in self.market_events}
        fill_by_id: dict[SimulatedFillId, SimulatedFill] = {}
        fills_by_order: dict[SimulatedOrderId, list[SimulatedFill]] = {}
        for fill in self.fills:
            self._require_run_ownership(fill)
            source_order = order_by_id.get(fill.order_id)
            if source_order is None:
                raise ValueError("fill references a missing simulated order")
            validate_fill_against_order(fill, source_order)
            if market_by_id.get(fill.market_event.market_event_id) != fill.market_event:
                raise ValueError("fill source market artifact is missing or differs")
            fill_by_id[fill.fill_id] = fill
            fills_by_order.setdefault(fill.order_id, []).append(fill)
            add(
                ReplayPayloadKind.SIMULATED_FILL,
                fill.fill_id,
                fill.fill_at,
                ReplayPhase.FILL,
            )
        resolution_orders: set[SimulatedOrderId] = set()
        for resolution in self.execution_resolutions:
            if resolution.run_id != run_id:
                raise ValueError("execution resolution belongs to a foreign run")
            resolved_order = order_by_id.get(resolution.order_id)
            if resolved_order is None:
                raise ValueError("execution resolution references a missing simulated order")
            if resolution.order_id in resolution_orders:
                raise ValueError("simulated order has multiple terminal execution resolutions")
            resolution_orders.add(resolution.order_id)
            order_fills = fills_by_order.get(resolution.order_id, [])
            if resolution.resolved_at < resolved_order.submitted_at:
                raise ValueError("execution resolution predates order submission")
            if resolution.source_market_event_id is not None:
                source = market_by_id.get(resolution.source_market_event_id)
                if source is None:
                    raise ValueError("execution resolution references a missing market event")
                if source.instrument_id != resolved_order.instrument_id:
                    raise ValueError("execution resolution market instrument differs from order")
                if (
                    resolution.outcome is ExecutionResolutionOutcome.REJECTED
                    and resolution.reason is ExecutionResolutionReason.INSUFFICIENT_LIQUIDITY
                    and resolution.resolved_at != source.available_at
                ):
                    raise ValueError(
                        "liquidity rejection must resolve when its source is available"
                    )
            if resolution.outcome is ExecutionResolutionOutcome.FILL_READY:
                source_market_event_id = resolution.source_market_event_id
                assert source_market_event_id is not None
                source = market_by_id.get(source_market_event_id)
                assert source is not None
                if len(order_fills) != 1:
                    raise ValueError("fill-ready resolution requires exactly one matching fill")
                fill = order_fills[0]
                if (
                    fill.market_event != source
                    or fill.fill_at != resolution.resolved_at
                    or source.available_at != resolution.resolved_at
                ):
                    raise ValueError("fill-ready resolution does not match its terminal fill")
            else:
                if order_fills:
                    raise ValueError("unfilled terminal execution resolution cannot have a fill")
                if (
                    resolution.outcome is ExecutionResolutionOutcome.EXPIRED_UNFILLED
                    and resolution.resolved_at < resolved_order.valid_until
                ):
                    raise ValueError("expired resolution predates order validity expiry")
            add(
                ReplayPayloadKind.EXECUTION_RESOLUTION,
                resolution.payload_id,
                resolution.resolved_at,
                ReplayPhase.EXECUTION_RESOLUTION,
            )
        if any(order_id not in resolution_orders for order_id in fills_by_order):
            raise ValueError("simulated fill has no terminal fill-ready resolution")
        for change in self.position_changes:
            self._require_run_ownership(change)
            applied_fill = fill_by_id.get(change.fill_id)
            source_order = order_by_id.get(change.order_id)
            if applied_fill is None or source_order is None:
                raise ValueError("position change references a missing fill or order")
            if (
                applied_fill.order_id != change.order_id
                or applied_fill.proposal_id != change.proposal_id
                or source_order.management_mandate_id != change.management_mandate_id
                or applied_fill.fill_at != change.changed_at
            ):
                raise ValueError("position change references a foreign or unrelated fill")
            add(
                ReplayPayloadKind.POSITION_CHANGE,
                change.position_change_id,
                change.changed_at,
                ReplayPhase.PORTFOLIO_UPDATE,
            )
        portfolio_by_id = {item.portfolio_snapshot_id: item for item in self.portfolio_snapshots}
        for portfolio in self.portfolio_snapshots:
            self._require_run_ownership(portfolio)
            if portfolio.starting_capital != self.manifest.starting_capital:
                raise ValueError("portfolio starting capital differs from run manifest")
            add(
                ReplayPayloadKind.PORTFOLIO_SNAPSHOT,
                portfolio.portfolio_snapshot_id,
                portfolio.as_of,
                ReplayPhase.PORTFOLIO_UPDATE,
            )
        trade_by_id = {item.realized_trade_result_id: item for item in self.realized_trades}
        for trade in self.realized_trades:
            self._require_run_ownership(trade)
            if trade.strategy_id != self.manifest.strategy_id:
                raise ValueError("realized trade strategy differs from run manifest")
            add(
                ReplayPayloadKind.REALIZED_TRADE,
                trade.realized_trade_result_id,
                trade.closed_at,
                ReplayPhase.PORTFOLIO_UPDATE,
            )
        finalization = self.finalizations[0]
        if finalization.run_id != run_id:
            raise ValueError("result finalization belongs to a foreign run")
        final_portfolio = portfolio_by_id.get(finalization.final_portfolio_snapshot_id)
        if final_portfolio is None:
            raise ValueError("result finalization references a missing final portfolio")
        if set(finalization.realized_trade_result_ids) != set(trade_by_id):
            raise ValueError("result finalization realized trades do not match artifact")
        if finalization.status is SimulationResultStatus.COMPLETE:
            if set(order_by_id) != resolution_orders:
                raise ValueError("complete result requires one terminal resolution per order")
            if final_portfolio != max(
                self.portfolio_snapshots,
                key=lambda item: (item.as_of, str(item.portfolio_snapshot_id)),
            ):
                raise ValueError("complete result does not reference the latest portfolio")
            reconcile_complete_portfolio(
                self.manifest,
                self.events,
                self.fills,
                self.position_changes,
                self.portfolio_snapshots,
                self.realized_trades,
            )
            accounting_times = [
                *(fill.fill_at for fill in self.fills),
                *(change.changed_at for change in self.position_changes),
            ]
            if accounting_times and final_portfolio.as_of < max(accounting_times):
                raise ValueError("complete result final portfolio predates fill accounting")
        if finalization.finalized_at < max(
            [final_portfolio.as_of, *(trade.closed_at for trade in self.realized_trades)]
        ):
            raise ValueError("result finalization predates reconciled accounting")
        add(
            ReplayPayloadKind.RUN_RESULT,
            finalization.payload_id,
            finalization.finalized_at,
            ReplayPhase.RESULT_FINALIZATION,
        )

        registry = {(item.kind, item.payload_id): item for item in bindings}
        if len(registry) != len(bindings):
            raise ValueError("replay artifact contains duplicate payload identities")
        references = [(event.payload_kind, event.payload_id) for event in self.events]
        if len(set(references)) != len(references):
            raise ValueError("replay trace references one payload more than once")
        if set(references) != set(registry):
            raise ValueError("replay trace contains missing or unreferenced typed payloads")
        for event in self.events:
            binding = registry[(event.payload_kind, event.payload_id)]
            if event.run_id != run_id or event.phase is not binding.phase:
                raise ValueError("replay event phase or run differs from typed payload")
            if event.scheduled_at != binding.causal_at:
                raise ValueError("replay event timestamp differs from typed payload causality")
        if self.events[-1].payload_kind is not ReplayPayloadKind.RUN_RESULT:
            raise ValueError("result finalization must be the final replay event")
        if finalization.finalized_at < max(event.scheduled_at for event in self.events[:-1]):
            raise ValueError("result finalization predates the replay trace")
        if self.artifact_id != calculate_replay_artifact_id(self):
            raise ValueError("replay artifact identity does not match content")
        return self

    def _require_run_ownership(
        self,
        payload: SimulatedOrder
        | SimulatedFill
        | PositionChange
        | PortfolioSnapshot
        | RealizedTradeResult,
    ) -> None:
        if (
            payload.run_id != self.manifest.run_id
            or payload.account_id != self.manifest.account_id
            or payload.allocation_id != self.manifest.allocation_id
            or payload.agent_id != self.manifest.agent_id
        ):
            raise ValueError("payload run or ownership differs from run manifest")


def calculate_replay_artifact_id(
    artifact: ReplayArtifactBundle | dict[str, object],
) -> ReplayArtifactId:
    return ReplayArtifactId.parse(sha256_content_id_v2(_without_id(artifact, "artifact_id")))


class SimulationResult(BaseModel):
    """A result whose linkage is re-derived from one validated replay artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result_id: SimulationResultId
    schema_version: Literal["simulation-result-v2"] = "simulation-result-v2"
    artifact: ReplayArtifactBundle
    run_id: SimulationRunId
    status: SimulationResultStatus
    replay_trace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_ids: tuple[ReplayEventId, ...] = Field(min_length=1)
    final_portfolio_snapshot_id: PortfolioSnapshotId
    realized_trade_result_ids: tuple[RealizedTradeResultId, ...] = ()
    finalized_at: datetime

    @classmethod
    def create(cls, artifact: ReplayArtifactBundle) -> SimulationResult:
        finalization = artifact.finalizations[0]
        content: dict[str, object] = {
            "schema_version": "simulation-result-v2",
            "artifact": artifact,
            "run_id": artifact.manifest.run_id,
            "status": finalization.status,
            "replay_trace_sha256": calculate_replay_trace_hash(artifact.events),
            "event_ids": tuple(event.replay_event_id for event in artifact.events),
            "final_portfolio_snapshot_id": finalization.final_portfolio_snapshot_id,
            "realized_trade_result_ids": finalization.realized_trade_result_ids,
            "finalized_at": finalization.finalized_at,
        }
        return cls.model_validate({"result_id": calculate_simulation_result_id(content), **content})

    @field_validator("finalized_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        finalization = self.artifact.finalizations[0]
        expected_event_ids = tuple(event.replay_event_id for event in self.artifact.events)
        expected_trace_hash = calculate_replay_trace_hash(self.artifact.events)
        if (
            self.run_id != self.artifact.manifest.run_id
            or self.status is not finalization.status
            or self.replay_trace_sha256 != expected_trace_hash
            or self.event_ids != expected_event_ids
            or self.final_portfolio_snapshot_id != finalization.final_portfolio_snapshot_id
            or self.realized_trade_result_ids != finalization.realized_trade_result_ids
            or self.finalized_at != finalization.finalized_at
        ):
            raise ValueError("simulation result does not match its validated replay artifact")
        if self.finalized_at < self.artifact.events[-1].scheduled_at:
            raise ValueError("simulation result finalization predates its final event")
        if self.result_id != calculate_simulation_result_id(self):
            raise ValueError("simulation result identity does not match content")
        return self


def calculate_simulation_result_id(
    result: SimulationResult | dict[str, object],
) -> SimulationResultId:
    return SimulationResultId.parse(sha256_content_id_v2(_without_id(result, "result_id")))
