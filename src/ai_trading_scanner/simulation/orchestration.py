"""One-event causal orchestration across the accepted Phase 2-5 contracts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_trading_scanner.domain import (
    AccountId,
    AgentId,
    AllocationId,
    ConfigurationVersionId,
    DatasetId,
    IndicatorConfigurationId,
    OrchestrationConfigurationId,
    OrchestrationResultId,
    ReplayArtifactId,
    ReplayScheduleId,
    RiskConfigurationId,
    SimulationRunId,
    StrategyConfigurationId,
    StrategyId,
    TransactionCostModelId,
)
from ai_trading_scanner.domain.content_identity import canonical_json_bytes, sha256_content_id_v2
from ai_trading_scanner.domain.execution import ExecutionDimensions
from ai_trading_scanner.indicators import (
    ATRConfig,
    EMAConfig,
    PriceBasis,
    ResetPolicy,
    RSIConfig,
    SmoothingMethod,
    VWAPConfig,
    calculate_atr,
    calculate_ema,
    calculate_rsi,
    calculate_vwap,
)
from ai_trading_scanner.market_data import (
    CanonicalDataset,
    CausalBarReader,
    HistoricalBar,
    MarketDataSlice,
)
from ai_trading_scanner.risk import (
    AllocationSnapshot,
    InMemoryCapitalCoordinator,
    ParentCapitalSnapshot,
    ReservationAttempt,
    ReservationAttemptStatus,
    RiskConfiguration,
    RiskDecisionStatus,
    RiskEngine,
    UnknownCapitalScopeError,
)
from ai_trading_scanner.simulation.artifacts import ReplayArtifactBundle
from ai_trading_scanner.simulation.models import (
    MarketEventReference,
    ReplayEvent,
    ReplayPayloadKind,
)
from ai_trading_scanner.simulation.scheduler import DeterministicReplayScheduler
from ai_trading_scanner.strategies import (
    IndicatorSnapshot,
    NoTradeDecision,
    ProposalAuthorityContext,
    RoundTripCostEstimate,
    StrategyConfiguration,
    StrategyEvaluationContext,
    TradeProposalDecision,
    calculate_strategy_configuration_id,
    evaluate_strategy,
)


class OrchestrationInvariantError(ValueError):
    """Raised when causal or ownership evidence cannot be resolved exactly."""


class OrchestrationOutcome(StrEnum):
    NO_TRADE = "NO_TRADE"
    RISK_REJECTED = "RISK_REJECTED"
    CAPITAL_RESERVED = "CAPITAL_RESERVED"


def _without_id(value: BaseModel | dict[str, object], field: str) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude={field})
    return {key: item for key, item in value.items() if key != field}


def calculate_orchestration_configuration_id(
    *,
    strategy_configuration: StrategyConfiguration,
    risk_configuration: RiskConfiguration,
    cost_estimate: RoundTripCostEstimate,
    artifact: ReplayArtifactBundle,
) -> OrchestrationConfigurationId:
    """Bind the exact decision inputs that are not contained in market evidence."""
    return OrchestrationConfigurationId.parse(
        sha256_content_id_v2(
            {
                "schema_version": "causal-orchestration-configuration-v1",
                "strategy_configuration": strategy_configuration,
                "risk_configuration": risk_configuration,
                "cost_estimate": cost_estimate,
                "manifest_configuration_version_id": artifact.manifest.configuration_version_id,
                "execution_dimensions": artifact.manifest.execution_dimensions,
                "cost_model_id": artifact.manifest.cost_model_id,
            }
        )
    )


class CausalOrchestrationResult(BaseModel):
    """Immutable evidence for one market-release-driven strategy evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    orchestration_result_id: OrchestrationResultId
    schema_version: Literal["causal-orchestration-result-v1"] = "causal-orchestration-result-v1"
    artifact_id: ReplayArtifactId
    orchestration_configuration_id: OrchestrationConfigurationId
    run_id: SimulationRunId
    dataset_id: DatasetId
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    strategy_id: StrategyId
    strategy_configuration_id: StrategyConfigurationId
    indicator_configuration_ids: tuple[IndicatorConfigurationId, ...] = Field(min_length=1)
    risk_configuration_id: RiskConfigurationId
    configuration_version_id: ConfigurationVersionId
    cost_model_id: TransactionCostModelId
    cost_methodology_version_id: ConfigurationVersionId
    execution_dimensions: ExecutionDimensions
    schedule_id: ReplayScheduleId
    scheduler_event_position: int = Field(ge=0)
    scheduler_position_after: int = Field(gt=0)
    triggering_event: ReplayEvent
    triggering_market_event: MarketEventReference
    released_market_events: tuple[MarketEventReference, ...] = Field(min_length=1)
    market_data: MarketDataSlice
    indicators: IndicatorSnapshot
    strategy_decision: NoTradeDecision | TradeProposalDecision
    risk_attempt: ReservationAttempt | None = None
    parent_snapshot_after: ParentCapitalSnapshot | None = None
    allocation_snapshot_after: AllocationSnapshot | None = None
    outcome: OrchestrationOutcome
    causal_parent_ids: tuple[str, ...] = Field(min_length=5)
    evaluated_at: datetime

    @classmethod
    def create(cls, **content: object) -> CausalOrchestrationResult:
        content.setdefault("schema_version", "causal-orchestration-result-v1")
        content["causal_parent_ids"] = _causal_parent_ids(content)
        return cls.model_validate(
            {
                "orchestration_result_id": calculate_orchestration_result_id(content),
                **content,
            }
        )

    @field_validator("evaluated_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("orchestration evaluation time must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        event = self.triggering_event
        market = self.triggering_market_event
        decision = self.strategy_decision
        if self.scheduler_position_after != self.scheduler_event_position + 1:
            raise ValueError("orchestration scheduler positions must advance exactly once")
        if (
            event.run_id != self.run_id
            or str(event.replay_event_id) not in self.causal_parent_ids
            or event.payload_kind is not ReplayPayloadKind.MARKET_EVENT
            or event.payload_id != str(market.market_event_id)
            or event.scheduled_at != market.available_at
        ):
            raise ValueError("triggering scheduler and market evidence are inconsistent")
        if not self.released_market_events or self.released_market_events[-1] != market:
            raise ValueError("triggering market event must be the newest released evidence")
        released_ids = tuple(str(item.market_event_id) for item in self.released_market_events)
        if len(set(released_ids)) != len(released_ids):
            raise ValueError("released market evidence cannot contain duplicates")
        if any(
            item.dataset_id != self.dataset_id or item.available_at > self.evaluated_at
            for item in self.released_market_events
        ):
            raise ValueError("released market evidence has foreign or future data")
        visible_keys = {_market_reference_key(item) for item in self.released_market_events}
        if any(_bar_reference_key(bar) not in visible_keys for bar in self.market_data.bars):
            raise ValueError("strategy market slice contains unreleased data")
        if any(bar.available_at > self.evaluated_at for bar in self.market_data.bars):
            raise ValueError("strategy market slice contains future-unavailable data")
        if hashlib.sha256(canonical_json_bytes(self.market_data.bars)).hexdigest() != (
            self.market_data.content_hash_sha256
        ):
            raise ValueError("strategy market slice hash does not match visible bars")
        if (
            self.market_data.dataset_id != self.dataset_id
            or market.dataset_id != self.dataset_id
            or market.instrument_id not in {bar.instrument_id for bar in self.market_data.bars}
            or self.evaluated_at != event.scheduled_at
            or decision.as_of != self.evaluated_at
            or decision.agent_id != self.agent_id
            or decision.strategy_id != self.strategy_id
            or decision.strategy_configuration_id != self.strategy_configuration_id
            or decision.dataset_id != self.dataset_id
            or decision.market_data_slice_hash_sha256 != self.market_data.content_hash_sha256
            or decision.indicator_configuration_ids != self.indicator_configuration_ids
            or self.indicators.configuration_ids != self.indicator_configuration_ids
        ):
            raise ValueError("strategy decision is not bound to visible causal evidence")
        if self.run_id != event.run_id:
            raise ValueError("orchestration result belongs to a foreign run")
        if self.outcome is OrchestrationOutcome.NO_TRADE:
            if not isinstance(decision, NoTradeDecision) or any(
                value is not None
                for value in (
                    self.risk_attempt,
                    self.parent_snapshot_after,
                    self.allocation_snapshot_after,
                )
            ):
                raise ValueError("NO_TRADE cannot carry risk or allocation effects")
        else:
            if not isinstance(decision, TradeProposalDecision) or self.risk_attempt is None:
                raise ValueError("proposal orchestration requires Phase 5 evidence")
            risk = self.risk_attempt.risk_decision
            if (
                risk.source_proposal != decision.proposal
                or risk.risk_configuration_id != self.risk_configuration_id
                or risk.source_risk_configuration.authority_configuration_version_id
                != self.configuration_version_id
                or risk.account_id != self.account_id
                or risk.allocation_id != self.allocation_id
                or risk.agent_id != self.agent_id
                or self.parent_snapshot_after is None
                or self.allocation_snapshot_after is None
                or self.parent_snapshot_after.account_id != self.account_id
                or self.allocation_snapshot_after.account_id != self.account_id
                or self.allocation_snapshot_after.allocation_id != self.allocation_id
                or self.allocation_snapshot_after.agent_id != self.agent_id
                or decision.proposal.authority_context.configuration_version_id
                != self.configuration_version_id
                or decision.proposal.authority_context.execution_dimensions
                != self.execution_dimensions
            ):
                raise ValueError("risk/allocation evidence has inconsistent ownership")
            if self.outcome is OrchestrationOutcome.RISK_REJECTED:
                if (
                    self.risk_attempt.status is not ReservationAttemptStatus.REJECTED
                    or risk.status is not RiskDecisionStatus.REJECTED
                ):
                    raise ValueError("risk-rejected outcome requires rejected Phase 5 evidence")
            elif (
                self.risk_attempt.status is not ReservationAttemptStatus.RESERVED
                or risk.status is not RiskDecisionStatus.APPROVED_FOR_RESERVATION
                or self.risk_attempt.reservation is None
            ):
                raise ValueError("capital-reserved outcome requires reservation evidence")
        if self.causal_parent_ids != _causal_parent_ids(self.model_dump(mode="python")):
            raise ValueError("causal parent identities do not match bound evidence")
        if self.orchestration_result_id != calculate_orchestration_result_id(self):
            raise ValueError("orchestration result identity does not match content")
        return self


def _causal_parent_ids(content: dict[str, object]) -> tuple[str, ...]:
    event = ReplayEvent.model_validate(content["triggering_event"])
    released_value = content["released_market_events"]
    if not isinstance(released_value, tuple | list):
        raise TypeError("released market evidence must be a sequence")
    released = tuple(MarketEventReference.model_validate(item) for item in released_value)
    decision_value = content["strategy_decision"]
    if isinstance(decision_value, dict):
        decision_id = str(decision_value["decision_id"])
    elif isinstance(decision_value, NoTradeDecision | TradeProposalDecision):
        decision_id = str(decision_value.decision_id)
    else:
        raise TypeError("strategy decision evidence has an unsupported type")
    parents = [
        str(content["artifact_id"]),
        str(content["schedule_id"]),
        str(event.replay_event_id),
        *(str(item.market_event_id) for item in released),
        decision_id,
    ]
    attempt_value = content.get("risk_attempt")
    if attempt_value is not None:
        attempt = ReservationAttempt.model_validate(attempt_value)
        risk = attempt.risk_decision
        parents.append(str(risk.risk_decision_id))
        if risk.sizing_decision is not None:
            parents.append(str(risk.sizing_decision.sizing_decision_id))
        if attempt.reservation is not None:
            parents.append(str(attempt.reservation.reservation_id))
    return tuple(parents)


def calculate_orchestration_result_id(
    result: CausalOrchestrationResult | dict[str, object],
) -> OrchestrationResultId:
    return OrchestrationResultId.parse(
        sha256_content_id_v2(_without_id(result, "orchestration_result_id"))
    )


def _market_reference_key(reference: MarketEventReference) -> tuple[object, ...]:
    return (
        reference.instrument_id,
        reference.interval_start_at,
        reference.event_at,
        reference.available_at,
        reference.source_record_id,
    )


def _bar_reference_key(bar: HistoricalBar) -> tuple[object, ...]:
    return (
        bar.instrument_id,
        bar.start_at,
        bar.end_at,
        bar.available_at,
        bar.source_record_id,
    )


@dataclass(slots=True)
class _OrchestrationCursorState:
    configuration_id: OrchestrationConfigurationId
    coordinator: InMemoryCapitalCoordinator
    lock: Lock


_ORCHESTRATION_CURSOR_STATES: dict[ReplayScheduleId, _OrchestrationCursorState] = {}
_ORCHESTRATION_CURSOR_STATES_LOCK = Lock()


def _orchestration_state_for(
    schedule_id: ReplayScheduleId,
    configuration_id: OrchestrationConfigurationId,
    coordinator: InMemoryCapitalCoordinator,
) -> _OrchestrationCursorState:
    with _ORCHESTRATION_CURSOR_STATES_LOCK:
        state = _ORCHESTRATION_CURSOR_STATES.get(schedule_id)
        if state is None:
            state = _OrchestrationCursorState(
                configuration_id=configuration_id,
                coordinator=coordinator,
                lock=Lock(),
            )
            _ORCHESTRATION_CURSOR_STATES[schedule_id] = state
            return state
        if state.configuration_id != configuration_id or state.coordinator is not coordinator:
            raise OrchestrationInvariantError(
                "one process-local schedule cannot use conflicting orchestration state"
            )
        return state


class CausalOrchestrator:
    """Advance one scheduler event and evaluate only a newly released market bar."""

    def __init__(
        self,
        *,
        artifact: ReplayArtifactBundle,
        dataset: CanonicalDataset,
        strategy_configuration: StrategyConfiguration,
        risk_configuration: RiskConfiguration,
        cost_estimate: RoundTripCostEstimate,
        capital_coordinator: InMemoryCapitalCoordinator,
    ) -> None:
        validated_artifact = ReplayArtifactBundle.model_validate(artifact.model_dump(mode="python"))
        rebuilt_dataset = CanonicalDataset.create(dataset.provenance, dataset.bars)
        if rebuilt_dataset != dataset:
            raise OrchestrationInvariantError(
                "canonical dataset identity or quality evidence differs"
            )
        strategy_type = type(strategy_configuration)
        validated_strategy = strategy_type.model_validate(
            strategy_configuration.model_dump(mode="python")
        )
        validated_risk = RiskConfiguration.model_validate(
            risk_configuration.model_dump(mode="python")
        )
        validated_cost = RoundTripCostEstimate.model_validate(
            cost_estimate.model_dump(mode="python")
        )
        manifest = validated_artifact.manifest
        expected_strategy_id = calculate_strategy_configuration_id(validated_strategy)
        if (
            rebuilt_dataset.dataset_id != manifest.dataset_id
            or validated_strategy.strategy_id != manifest.strategy_id
            or expected_strategy_id != manifest.strategy_configuration_id
            or validated_strategy.strategy_version != manifest.strategy_version
            or validated_risk.risk_configuration_id != manifest.risk_configuration_id
            or validated_risk.authority_configuration_version_id
            != manifest.configuration_version_id
        ):
            raise OrchestrationInvariantError(
                "dataset, strategy, risk, or authority configuration differs from manifest"
            )
        indicator_ids = _indicator_snapshot_configuration_ids(validated_strategy)
        if indicator_ids != manifest.indicator_configuration_ids:
            raise OrchestrationInvariantError(
                "strategy indicator configuration identities differ from manifest"
            )
        try:
            state = capital_coordinator.evaluation_state(
                manifest.account_id, manifest.allocation_id
            )
        except UnknownCapitalScopeError as error:
            raise OrchestrationInvariantError(
                "capital coordinator does not contain the manifest allocation scope"
            ) from error
        if (
            state.parent.account_id != manifest.account_id
            or state.allocation.account_id != manifest.account_id
            or state.allocation.allocation_id != manifest.allocation_id
            or state.allocation.agent_id != manifest.agent_id
            or state.allocation.configuration_version_id != manifest.configuration_version_id
        ):
            raise OrchestrationInvariantError("capital coordinator ownership differs from manifest")
        bars_by_key = {_bar_reference_key(bar): bar for bar in rebuilt_dataset.bars}
        market_by_id: dict[str, MarketEventReference] = {}
        bar_by_market_id: dict[str, HistoricalBar] = {}
        for reference in validated_artifact.market_events:
            bar = bars_by_key.get(_market_reference_key(reference))
            if bar is None:
                raise OrchestrationInvariantError(
                    "market event cannot be resolved to one canonical dataset bar"
                )
            market_by_id[str(reference.market_event_id)] = reference
            bar_by_market_id[str(reference.market_event_id)] = bar

        self._artifact = validated_artifact
        self._reader = CausalBarReader(rebuilt_dataset)
        self._strategy_configuration = validated_strategy
        self._risk_configuration = validated_risk
        self._cost_estimate = validated_cost
        self._coordinator = capital_coordinator
        self._risk_engine = RiskEngine()
        self._market_by_id = market_by_id
        self._bar_by_market_id = bar_by_market_id
        self._scheduler = DeterministicReplayScheduler.from_artifact(validated_artifact)
        self._configuration_id = calculate_orchestration_configuration_id(
            strategy_configuration=validated_strategy,
            risk_configuration=validated_risk,
            cost_estimate=validated_cost,
            artifact=validated_artifact,
        )
        self._state = _orchestration_state_for(
            self._scheduler.schedule_id,
            self._configuration_id,
            capital_coordinator,
        )

    @property
    def scheduler(self) -> DeterministicReplayScheduler:
        return self._scheduler

    @property
    def released_market_events(self) -> tuple[MarketEventReference, ...]:
        with self._state.lock:
            return self._released_prefix()

    def advance(self) -> CausalOrchestrationResult | None:
        """Consume exactly one authorized event; evaluate only MARKET_EVENT payloads."""
        with self._state.lock:
            event_position = self._scheduler.position
            event = self._scheduler.next_event()
            if event.payload_kind is not ReplayPayloadKind.MARKET_EVENT:
                return None
            reference = self._market_by_id.get(event.payload_id)
            if reference is None:
                raise OrchestrationInvariantError(
                    "scheduled market dependency is absent from the validated registry"
                )
            bar = self._bar_by_market_id.get(event.payload_id)
            if bar is None:
                raise OrchestrationInvariantError(
                    "scheduled market dependency is absent from the canonical dataset"
                )
            released_market_events = self._released_prefix()
            if self._scheduler.position != event_position + 1:
                raise OrchestrationInvariantError(
                    "scheduler advanced concurrently outside this orchestration step"
                )
            if not released_market_events or released_market_events[-1] != reference:
                raise OrchestrationInvariantError(
                    "scheduler consumed prefix does not end with the triggering market event"
                )
            market_data = self._visible_slice(
                reference,
                bar,
                event.scheduled_at,
                released_market_events,
            )
            indicators = _indicator_snapshot(market_data, self._strategy_configuration)
            manifest = self._artifact.manifest
            context = StrategyEvaluationContext(
                agent_id=manifest.agent_id,
                strategy_id=manifest.strategy_id,
                strategy_configuration_id=manifest.strategy_configuration_id,
                instrument_id=reference.instrument_id,
                as_of=event.scheduled_at,
                market_data=market_data,
                indicators=indicators,
                cost_estimate=self._cost_estimate,
                authority_context=ProposalAuthorityContext(
                    configuration_version_id=manifest.configuration_version_id,
                    execution_dimensions=manifest.execution_dimensions,
                ),
            )
            decision = evaluate_strategy(context, self._strategy_configuration)
            risk_attempt: ReservationAttempt | None = None
            parent_after: ParentCapitalSnapshot | None = None
            allocation_after: AllocationSnapshot | None = None
            if isinstance(decision, NoTradeDecision):
                outcome = OrchestrationOutcome.NO_TRADE
            else:
                if (
                    decision.proposal.management_mandate.mandate_id
                    != manifest.management_mandate_id
                ):
                    raise OrchestrationInvariantError(
                        "proposal management mandate differs from run manifest"
                    )
                state = self._coordinator.evaluation_state(
                    manifest.account_id, manifest.allocation_id
                )
                preliminary = self._risk_engine.evaluate(
                    decision.proposal,
                    self._risk_configuration,
                    state,
                    evaluated_at=event.scheduled_at,
                )
                if preliminary.status is RiskDecisionStatus.REJECTED:
                    risk_attempt = ReservationAttempt(
                        status=ReservationAttemptStatus.REJECTED,
                        risk_decision=preliminary,
                    )
                else:
                    risk_attempt = self._coordinator.reserve(
                        decision.proposal,
                        self._risk_configuration,
                        preliminary,
                        account_id=manifest.account_id,
                        allocation_id=manifest.allocation_id,
                        evaluated_at=event.scheduled_at,
                    )
                parent_after = self._coordinator.parent_snapshot(manifest.account_id)
                allocation_after = self._coordinator.allocation_snapshot(manifest.allocation_id)
                outcome = (
                    OrchestrationOutcome.CAPITAL_RESERVED
                    if risk_attempt.status is ReservationAttemptStatus.RESERVED
                    else OrchestrationOutcome.RISK_REJECTED
                )
            return CausalOrchestrationResult.create(
                artifact_id=self._artifact.artifact_id,
                orchestration_configuration_id=self._configuration_id,
                run_id=manifest.run_id,
                dataset_id=manifest.dataset_id,
                account_id=manifest.account_id,
                allocation_id=manifest.allocation_id,
                agent_id=manifest.agent_id,
                strategy_id=manifest.strategy_id,
                strategy_configuration_id=manifest.strategy_configuration_id,
                indicator_configuration_ids=manifest.indicator_configuration_ids,
                risk_configuration_id=manifest.risk_configuration_id,
                configuration_version_id=manifest.configuration_version_id,
                cost_model_id=manifest.cost_model_id,
                cost_methodology_version_id=self._cost_estimate.methodology_version_id,
                execution_dimensions=manifest.execution_dimensions,
                schedule_id=self._scheduler.schedule_id,
                scheduler_event_position=event_position,
                scheduler_position_after=self._scheduler.position,
                triggering_event=event,
                triggering_market_event=reference,
                released_market_events=released_market_events,
                market_data=market_data,
                indicators=indicators,
                strategy_decision=decision,
                risk_attempt=risk_attempt,
                parent_snapshot_after=parent_after,
                allocation_snapshot_after=allocation_after,
                outcome=outcome,
                evaluated_at=event.scheduled_at,
            )

    def _visible_slice(
        self,
        reference: MarketEventReference,
        triggering_bar: HistoricalBar,
        as_of: datetime,
        released_market_events: tuple[MarketEventReference, ...],
    ) -> MarketDataSlice:
        reader_slice = self._reader.slice_as_of(as_of, frozenset({reference.instrument_id}))
        released_keys = {
            _market_reference_key(item)
            for item in released_market_events
            if item.instrument_id == reference.instrument_id
        }
        bars = tuple(
            bar
            for bar in reader_slice.bars
            if _bar_reference_key(bar) in released_keys
            and bar.session_id == triggering_bar.session_id
        )
        if triggering_bar not in bars:
            raise OrchestrationInvariantError("triggering bar is not causally visible")
        first_start = min(bar.start_at for bar in bars)
        latest_end = max(bar.end_at for bar in bars)
        visible_findings = tuple(
            finding
            for finding in reader_slice.quality_findings
            if (
                (finding.start_at is None and finding.end_at is None)
                or (
                    finding.start_at is not None
                    and finding.end_at is not None
                    and first_start <= finding.start_at
                    and finding.end_at <= latest_end
                )
            )
        )
        return MarketDataSlice(
            dataset_id=reader_slice.dataset_id,
            as_of=as_of,
            bars=bars,
            content_hash_sha256=hashlib.sha256(canonical_json_bytes(bars)).hexdigest(),
            quality_findings=visible_findings,
        )

    def _released_prefix(self) -> tuple[MarketEventReference, ...]:
        released: list[MarketEventReference] = []
        for event in self._scheduler.schedule.events[: self._scheduler.position]:
            if event.payload_kind is not ReplayPayloadKind.MARKET_EVENT:
                continue
            reference = self._market_by_id.get(event.payload_id)
            if reference is None:
                raise OrchestrationInvariantError(
                    "consumed market dependency is absent from the validated registry"
                )
            released.append(reference)
        return tuple(released)


def _indicator_configurations(
    configuration: StrategyConfiguration,
) -> tuple[EMAConfig, EMAConfig, EMAConfig, RSIConfig, ATRConfig, VWAPConfig]:
    return (
        EMAConfig(period=configuration.ema_fast_period),
        EMAConfig(period=configuration.ema_medium_period),
        EMAConfig(period=configuration.ema_slow_period),
        RSIConfig(period=configuration.rsi_period, smoothing=SmoothingMethod.WILDER),
        ATRConfig(period=configuration.atr_period, smoothing=SmoothingMethod.WILDER),
        VWAPConfig(price_basis=PriceBasis.TYPICAL_PRICE, reset_policy=ResetPolicy.SESSION),
    )


def _indicator_snapshot_configuration_ids(
    configuration: StrategyConfiguration,
) -> tuple[IndicatorConfigurationId, ...]:
    from ai_trading_scanner.indicators import calculate_indicator_configuration_id

    return tuple(
        sorted(
            (
                calculate_indicator_configuration_id(item)
                for item in _indicator_configurations(configuration)
            ),
            key=str,
        )
    )


def _indicator_snapshot(
    market_data: MarketDataSlice, configuration: StrategyConfiguration
) -> IndicatorSnapshot:
    fast, medium, slow, rsi, atr, vwap = _indicator_configurations(configuration)
    return IndicatorSnapshot(
        ema_fast=calculate_ema(market_data, fast),
        ema_medium=calculate_ema(market_data, medium),
        ema_slow=calculate_ema(market_data, slow),
        rsi=calculate_rsi(market_data, rsi),
        atr=calculate_atr(market_data, atr),
        session_vwap=calculate_vwap(market_data, vwap),
    )
