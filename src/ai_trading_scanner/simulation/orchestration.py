"""One-event causal orchestration across the accepted Phase 2-5 contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

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
from ai_trading_scanner.simulation.scheduler import (
    DeterministicReplayScheduler,
    ReplaySchedule,
    _LeasedSchedulerTransition,
    _OrchestrationSchedulerLease,
)
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


class OrchestrationSchedulerView(BaseModel):
    """Read-only inspection of an orchestration-owned scheduler cursor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schedule: ReplaySchedule
    position: int = Field(ge=0)
    remaining: int = Field(ge=0)
    has_events: bool
    exhausted: bool
    published_result_ids: tuple[OrchestrationResultId, ...]

    @property
    def schedule_id(self) -> ReplayScheduleId:
        return self.schedule.schedule_id

    @property
    def run_id(self) -> SimulationRunId:
        return self.schedule.run_id

    @model_validator(mode="after")
    def validate_view(self) -> Self:
        if self.position + self.remaining != len(self.schedule.events):
            raise ValueError("orchestration scheduler view has inconsistent position")
        if self.has_events != (self.remaining > 0) or self.exhausted == self.has_events:
            raise ValueError("orchestration scheduler view has inconsistent exhaustion")
        return self


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


@dataclass(frozen=True, slots=True)
class _AuthoritativeResultEvidence:
    """Process-local immutable evidence captured by the orchestration transition."""

    indicators: IndicatorSnapshot
    strategy_decision: NoTradeDecision | TradeProposalDecision
    risk_attempt: ReservationAttempt | None
    parent_snapshot_before: ParentCapitalSnapshot | None
    allocation_snapshot_before: AllocationSnapshot | None
    parent_snapshot_after: ParentCapitalSnapshot | None
    allocation_snapshot_after: AllocationSnapshot | None
    outcome: OrchestrationOutcome


@dataclass(frozen=True, slots=True)
class _OrchestrationResultBinding:
    artifact: ReplayArtifactBundle
    dataset: CanonicalDataset
    schedule: ReplaySchedule
    strategy_configuration: StrategyConfiguration
    risk_configuration: RiskConfiguration
    cost_estimate: RoundTripCostEstimate
    orchestration_configuration_id: OrchestrationConfigurationId
    authoritative_evidence: _AuthoritativeResultEvidence
    recompute_phase34: bool


class CausalOrchestrationResult(BaseModel):
    """Immutable evidence for one market-release-driven strategy evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")

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
    def _create_from_transition(
        cls,
        *,
        artifact: ReplayArtifactBundle,
        dataset: CanonicalDataset,
        schedule: ReplaySchedule,
        strategy_configuration: StrategyConfiguration,
        risk_configuration: RiskConfiguration,
        cost_estimate: RoundTripCostEstimate,
        authoritative_evidence: _AuthoritativeResultEvidence,
        **content: object,
    ) -> CausalOrchestrationResult:
        """Create evidence only from its fully validated authoritative context."""
        binding = _result_binding(
            artifact=artifact,
            dataset=dataset,
            schedule=schedule,
            strategy_configuration=strategy_configuration,
            risk_configuration=risk_configuration,
            cost_estimate=cost_estimate,
            authoritative_evidence=authoritative_evidence,
            recompute_phase34=False,
        )
        manifest = binding.artifact.manifest
        content.update(
            {
                "artifact_id": binding.artifact.artifact_id,
                "orchestration_configuration_id": binding.orchestration_configuration_id,
                "run_id": manifest.run_id,
                "dataset_id": manifest.dataset_id,
                "account_id": manifest.account_id,
                "allocation_id": manifest.allocation_id,
                "agent_id": manifest.agent_id,
                "strategy_id": manifest.strategy_id,
                "strategy_configuration_id": manifest.strategy_configuration_id,
                "indicator_configuration_ids": manifest.indicator_configuration_ids,
                "risk_configuration_id": manifest.risk_configuration_id,
                "configuration_version_id": manifest.configuration_version_id,
                "cost_model_id": manifest.cost_model_id,
                "cost_methodology_version_id": binding.cost_estimate.methodology_version_id,
                "execution_dimensions": manifest.execution_dimensions,
                "schedule_id": binding.schedule.schedule_id,
                "indicators": authoritative_evidence.indicators,
                "strategy_decision": authoritative_evidence.strategy_decision,
                "risk_attempt": authoritative_evidence.risk_attempt,
                "parent_snapshot_after": authoritative_evidence.parent_snapshot_after,
                "allocation_snapshot_after": authoritative_evidence.allocation_snapshot_after,
                "outcome": authoritative_evidence.outcome,
            }
        )
        content.setdefault("schema_version", "causal-orchestration-result-v1")
        content["causal_parent_ids"] = _causal_parent_ids(content)
        return cls.model_validate(
            {
                "orchestration_result_id": calculate_orchestration_result_id(content),
                **content,
            },
            context={"orchestration_binding": binding},
        )

    @classmethod
    def _validate_reconstruction(
        cls,
        value: object,
        *,
        artifact: ReplayArtifactBundle,
        dataset: CanonicalDataset,
        schedule: ReplaySchedule,
        strategy_configuration: StrategyConfiguration,
        risk_configuration: RiskConfiguration,
        cost_estimate: RoundTripCostEstimate,
        authoritative_evidence: _AuthoritativeResultEvidence,
    ) -> CausalOrchestrationResult:
        """Reconstruct evidence only while rechecking its authoritative sources."""
        binding = _result_binding(
            artifact=artifact,
            dataset=dataset,
            schedule=schedule,
            strategy_configuration=strategy_configuration,
            risk_configuration=risk_configuration,
            cost_estimate=cost_estimate,
            authoritative_evidence=authoritative_evidence,
            recompute_phase34=True,
        )
        return cls.model_validate(value, context={"orchestration_binding": binding})

    @field_validator("evaluated_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("orchestration evaluation time must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_evidence(self, info: ValidationInfo) -> Self:
        binding = (info.context or {}).get("orchestration_binding")
        if not isinstance(binding, _OrchestrationResultBinding):
            raise ValueError("authoritative orchestration context is required")
        event = self.triggering_event
        market = self.triggering_market_event
        decision = self.strategy_decision
        schedule = binding.schedule
        artifact = binding.artifact
        manifest = artifact.manifest
        if ReplaySchedule.from_artifact(artifact) != schedule:
            raise ValueError("orchestration schedule is not derived from the artifact")
        if self.scheduler_event_position >= len(schedule.events):
            raise ValueError("orchestration scheduler position is outside the schedule")
        expected_event = schedule.events[self.scheduler_event_position]
        market_by_id = {str(item.market_event_id): item for item in artifact.market_events}
        expected_released = tuple(
            market_by_id[item.payload_id]
            for item in schedule.events[: self.scheduler_position_after]
            if item.payload_kind is ReplayPayloadKind.MARKET_EVENT
        )
        if self.scheduler_position_after != self.scheduler_event_position + 1:
            raise ValueError("orchestration scheduler positions must advance exactly once")
        if (
            event != expected_event
            or event.run_id != self.run_id
            or str(event.replay_event_id) not in self.causal_parent_ids
            or event.payload_kind is not ReplayPayloadKind.MARKET_EVENT
            or event.payload_id != str(market.market_event_id)
            or event.scheduled_at != market.available_at
        ):
            raise ValueError("triggering scheduler and market evidence are inconsistent")
        if self.released_market_events != expected_released:
            raise ValueError("released market evidence is not the exact consumed schedule prefix")
        if not self.released_market_events or self.released_market_events[-1] != market:
            raise ValueError("triggering market event must be the newest released evidence")
        expected_market_data = _authoritative_market_slice(
            binding.dataset,
            expected_released,
            market,
            event.scheduled_at,
        )
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
        if self.market_data != expected_market_data:
            raise ValueError("strategy market slice is not the exact authoritative causal slice")
        authoritative = binding.authoritative_evidence
        if binding.recompute_phase34:
            expected_indicators = _indicator_snapshot(
                expected_market_data, binding.strategy_configuration
            )
            expected_decision = evaluate_strategy(
                _strategy_evaluation_context(
                    artifact=artifact,
                    market=market,
                    market_data=expected_market_data,
                    indicators=expected_indicators,
                    cost_estimate=binding.cost_estimate,
                ),
                binding.strategy_configuration,
            )
            if (
                authoritative.indicators != expected_indicators
                or authoritative.strategy_decision != expected_decision
            ):
                raise ValueError(
                    "retained Phase 3/4 evidence differs from authoritative recomputation"
                )
        else:
            expected_indicators = authoritative.indicators
            expected_decision = authoritative.strategy_decision
        if self.indicators != expected_indicators:
            raise ValueError("indicator evidence differs from authoritative calculation")
        if decision != expected_decision:
            raise ValueError("strategy decision differs from authoritative evaluation")
        if (
            self.artifact_id != artifact.artifact_id
            or self.schedule_id != schedule.schedule_id
            or self.orchestration_configuration_id != binding.orchestration_configuration_id
            or self.run_id != manifest.run_id
            or self.dataset_id != manifest.dataset_id
            or self.account_id != manifest.account_id
            or self.allocation_id != manifest.allocation_id
            or self.agent_id != manifest.agent_id
            or self.strategy_id != manifest.strategy_id
            or self.strategy_configuration_id != manifest.strategy_configuration_id
            or self.indicator_configuration_ids != manifest.indicator_configuration_ids
            or self.risk_configuration_id != manifest.risk_configuration_id
            or self.configuration_version_id != manifest.configuration_version_id
            or self.cost_model_id != manifest.cost_model_id
            or self.cost_methodology_version_id != binding.cost_estimate.methodology_version_id
            or self.execution_dimensions != manifest.execution_dimensions
            or self.market_data.dataset_id != self.dataset_id
            or market.dataset_id != self.dataset_id
            or _market_reference_key(market)
            not in {_bar_reference_key(bar) for bar in self.market_data.bars}
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
        if (
            self.risk_attempt != authoritative.risk_attempt
            or self.parent_snapshot_after != authoritative.parent_snapshot_after
            or self.allocation_snapshot_after != authoritative.allocation_snapshot_after
            or self.outcome is not authoritative.outcome
        ):
            raise ValueError("Phase 5 evidence differs from the authoritative transaction")
        _validate_phase5_transition(authoritative)
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
            if decision.proposal.economics.cost_estimate != binding.cost_estimate:
                raise ValueError("proposal cost evidence differs from orchestration context")
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


def _result_position(value: object) -> int:
    if isinstance(value, CausalOrchestrationResult):
        return value.scheduler_event_position
    if isinstance(value, dict):
        position = value.get("scheduler_event_position")
        if isinstance(position, bool) or not isinstance(position, int) or position < 0:
            raise OrchestrationInvariantError(
                "result reconstruction requires a valid scheduler event position"
            )
        return position
    raise OrchestrationInvariantError("result reconstruction requires typed evidence or a mapping")


def _result_binding(
    *,
    artifact: ReplayArtifactBundle,
    dataset: CanonicalDataset,
    schedule: ReplaySchedule,
    strategy_configuration: StrategyConfiguration,
    risk_configuration: RiskConfiguration,
    cost_estimate: RoundTripCostEstimate,
    authoritative_evidence: _AuthoritativeResultEvidence,
    recompute_phase34: bool,
) -> _OrchestrationResultBinding:
    """Rebuild and cross-check every authoritative result dependency."""
    validated_artifact = ReplayArtifactBundle.model_validate(artifact.model_dump(mode="python"))
    validated_dataset = CanonicalDataset.create(dataset.provenance, dataset.bars)
    validated_schedule = ReplaySchedule.model_validate(schedule.model_dump(mode="python"))
    strategy_type = type(strategy_configuration)
    validated_strategy = strategy_type.model_validate(
        strategy_configuration.model_dump(mode="python")
    )
    validated_risk = RiskConfiguration.model_validate(risk_configuration.model_dump(mode="python"))
    validated_cost = RoundTripCostEstimate.model_validate(cost_estimate.model_dump(mode="python"))
    manifest = validated_artifact.manifest
    if validated_dataset != dataset or validated_dataset.dataset_id != manifest.dataset_id:
        raise OrchestrationInvariantError(
            "authoritative dataset identity differs from the orchestration artifact"
        )
    if ReplaySchedule.from_artifact(validated_artifact) != validated_schedule:
        raise OrchestrationInvariantError("schedule is not derived from the authoritative artifact")
    if (
        calculate_strategy_configuration_id(validated_strategy)
        != manifest.strategy_configuration_id
        or validated_strategy.strategy_id != manifest.strategy_id
        or validated_strategy.strategy_version != manifest.strategy_version
        or _indicator_snapshot_configuration_ids(validated_strategy)
        != manifest.indicator_configuration_ids
        or validated_risk.risk_configuration_id != manifest.risk_configuration_id
        or validated_risk.authority_configuration_version_id != manifest.configuration_version_id
    ):
        raise OrchestrationInvariantError(
            "result binding strategy, indicator, risk, or authority differs from manifest"
        )
    configuration_id = calculate_orchestration_configuration_id(
        strategy_configuration=validated_strategy,
        risk_configuration=validated_risk,
        cost_estimate=validated_cost,
        artifact=validated_artifact,
    )
    return _OrchestrationResultBinding(
        artifact=validated_artifact,
        dataset=validated_dataset,
        schedule=validated_schedule,
        strategy_configuration=validated_strategy,
        risk_configuration=validated_risk,
        cost_estimate=validated_cost,
        orchestration_configuration_id=configuration_id,
        authoritative_evidence=authoritative_evidence,
        recompute_phase34=recompute_phase34,
    )


def _authoritative_market_slice(
    dataset: CanonicalDataset,
    released_market_events: tuple[MarketEventReference, ...],
    triggering_market_event: MarketEventReference,
    as_of: datetime,
) -> MarketDataSlice:
    """Rebuild the exact same-session slice from the canonical consumed prefix."""
    bars_by_key = {_bar_reference_key(bar): bar for bar in dataset.bars}
    triggering_bar = bars_by_key.get(_market_reference_key(triggering_market_event))
    if triggering_bar is None:
        raise OrchestrationInvariantError(
            "triggering market event is absent from the authoritative dataset"
        )
    reader_slice = CausalBarReader(dataset).slice_as_of(
        as_of, frozenset({triggering_market_event.instrument_id})
    )
    released_keys = {
        _market_reference_key(item)
        for item in released_market_events
        if item.instrument_id == triggering_market_event.instrument_id
    }
    bars = tuple(
        bar
        for bar in reader_slice.bars
        if _bar_reference_key(bar) in released_keys and bar.session_id == triggering_bar.session_id
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


def _strategy_evaluation_context(
    *,
    artifact: ReplayArtifactBundle,
    market: MarketEventReference,
    market_data: MarketDataSlice,
    indicators: IndicatorSnapshot,
    cost_estimate: RoundTripCostEstimate,
) -> StrategyEvaluationContext:
    manifest = artifact.manifest
    return StrategyEvaluationContext(
        agent_id=manifest.agent_id,
        strategy_id=manifest.strategy_id,
        strategy_configuration_id=manifest.strategy_configuration_id,
        instrument_id=market.instrument_id,
        as_of=market.available_at,
        market_data=market_data,
        indicators=indicators,
        cost_estimate=cost_estimate,
        authority_context=ProposalAuthorityContext(
            configuration_version_id=manifest.configuration_version_id,
            execution_dimensions=manifest.execution_dimensions,
        ),
    )


def _validate_phase5_transition(evidence: _AuthoritativeResultEvidence) -> None:
    """Reconcile the exact coordinator-issued attempt with its capital transition."""
    attempt = evidence.risk_attempt
    before_parent = evidence.parent_snapshot_before
    before_allocation = evidence.allocation_snapshot_before
    after_parent = evidence.parent_snapshot_after
    after_allocation = evidence.allocation_snapshot_after
    if evidence.outcome is OrchestrationOutcome.NO_TRADE:
        if any(
            item is not None
            for item in (
                attempt,
                before_parent,
                before_allocation,
                after_parent,
                after_allocation,
            )
        ):
            raise ValueError("NO_TRADE cannot carry a Phase 5 transition")
        return
    if any(
        item is None
        for item in (
            attempt,
            before_parent,
            before_allocation,
            after_parent,
            after_allocation,
        )
    ):
        raise ValueError("proposal outcome requires complete Phase 5 transition evidence")
    assert attempt is not None
    assert before_parent is not None and before_allocation is not None
    assert after_parent is not None and after_allocation is not None
    risk = attempt.risk_decision
    if (
        before_parent.account_id != risk.account_id
        or before_allocation.account_id != risk.account_id
        or before_allocation.allocation_id != risk.allocation_id
        or before_allocation.agent_id != risk.agent_id
    ):
        raise ValueError("Phase 5 pre-transaction capital has foreign ownership")
    if evidence.outcome is OrchestrationOutcome.RISK_REJECTED:
        if (
            attempt.status is not ReservationAttemptStatus.REJECTED
            or risk.status is not RiskDecisionStatus.REJECTED
            or attempt.reservation is not None
            or after_parent != before_parent
            or after_allocation != before_allocation
        ):
            raise ValueError("rejected Phase 5 outcome changed capital or status")
        return
    reservation = attempt.reservation
    sizing = risk.sizing_decision
    if (
        evidence.outcome is not OrchestrationOutcome.CAPITAL_RESERVED
        or attempt.status is not ReservationAttemptStatus.RESERVED
        or risk.status is not RiskDecisionStatus.APPROVED_FOR_RESERVATION
        or reservation is None
        or sizing is None
        or attempt.idempotent_replay
    ):
        raise ValueError("accepted Phase 5 outcome lacks a fresh approved reservation")
    if (
        risk.source_evaluation_state.parent != before_parent
        or risk.source_evaluation_state.allocation != before_allocation
        or reservation.approved_quantity != sizing.quantity
        or reservation.reserved_amount != sizing.reservation_amount
        or reservation.reserved_downside != sizing.modeled_risk_amount
        or reservation.account_id != before_parent.account_id
        or reservation.allocation_id != before_allocation.allocation_id
        or reservation.agent_id != before_allocation.agent_id
    ):
        raise ValueError("reservation does not reconcile with sizing or pre-transaction capital")
    expected_parent = ParentCapitalSnapshot.model_validate(
        {
            **before_parent.model_dump(mode="python"),
            "available_capital": before_parent.available_capital - reservation.reserved_amount,
            "active_reserved_capital": before_parent.active_reserved_capital
            + reservation.reserved_amount,
            "revision": before_parent.revision + 1,
        }
    )
    expected_allocation = AllocationSnapshot.model_validate(
        {
            **before_allocation.model_dump(mode="python"),
            "available_capital": before_allocation.available_capital - reservation.reserved_amount,
            "active_reserved_capital": before_allocation.active_reserved_capital
            + reservation.reserved_amount,
            "active_reservation_count": before_allocation.active_reservation_count + 1,
            "revision": before_allocation.revision + 1,
        }
    )
    if after_parent != expected_parent or after_allocation != expected_allocation:
        raise ValueError("post-reservation capital does not match the exact reserved delta")


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
    scheduler_lease: _OrchestrationSchedulerLease
    published_results: dict[int, CausalOrchestrationResult]
    authoritative_evidence: dict[int, _AuthoritativeResultEvidence]
    lock: Lock


_ORCHESTRATION_CURSOR_STATES: dict[ReplayScheduleId, _OrchestrationCursorState] = {}
_ORCHESTRATION_CURSOR_STATES_LOCK = Lock()


def _orchestration_state_for(
    scheduler: DeterministicReplayScheduler,
    configuration_id: OrchestrationConfigurationId,
    coordinator: InMemoryCapitalCoordinator,
) -> _OrchestrationCursorState:
    with _ORCHESTRATION_CURSOR_STATES_LOCK:
        schedule_id = scheduler.schedule_id
        state = _ORCHESTRATION_CURSOR_STATES.get(schedule_id)
        if state is None:
            state = _OrchestrationCursorState(
                configuration_id=configuration_id,
                coordinator=coordinator,
                scheduler_lease=scheduler._lease_for_orchestration(),
                published_results={},
                authoritative_evidence={},
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
        self._dataset = rebuilt_dataset
        self._strategy_configuration = validated_strategy
        self._risk_configuration = validated_risk
        self._cost_estimate = validated_cost
        self._coordinator = capital_coordinator
        self._risk_engine = RiskEngine()
        self._market_by_id = market_by_id
        self._bar_by_market_id = bar_by_market_id
        scheduler = DeterministicReplayScheduler.from_artifact(validated_artifact)
        self._configuration_id = calculate_orchestration_configuration_id(
            strategy_configuration=validated_strategy,
            risk_configuration=validated_risk,
            cost_estimate=validated_cost,
            artifact=validated_artifact,
        )
        self._state = _orchestration_state_for(
            scheduler,
            self._configuration_id,
            capital_coordinator,
        )
        self._failure_injector: Callable[[str], None] | None = None

    @property
    def scheduler(self) -> OrchestrationSchedulerView:
        """Return immutable cursor status without exposing advancement authority."""
        with self._state.lock:
            position, _ = self._state.scheduler_lease.inspect()
            remaining = len(self._state.scheduler_lease.schedule.events) - position
            return OrchestrationSchedulerView(
                schedule=self._state.scheduler_lease.schedule,
                position=position,
                remaining=remaining,
                has_events=remaining > 0,
                exhausted=remaining == 0,
                published_result_ids=tuple(
                    self._state.published_results[index].orchestration_result_id
                    for index in sorted(self._state.published_results)
                ),
            )

    @property
    def released_market_events(self) -> tuple[MarketEventReference, ...]:
        with self._state.lock:
            position, _ = self._state.scheduler_lease.inspect()
            return self._released_prefix(position)

    def validate_result(self, value: object) -> CausalOrchestrationResult:
        """Validate reconstructed evidence against this orchestrator's frozen inputs."""
        position = _result_position(value)
        with self._state.lock:
            authoritative = self._state.authoritative_evidence.get(position)
            if authoritative is None:
                raise OrchestrationInvariantError(
                    "no committed authoritative evidence exists for the claimed event position"
                )
            return CausalOrchestrationResult._validate_reconstruction(
                value,
                artifact=self._artifact,
                dataset=self._dataset,
                schedule=self._state.scheduler_lease.schedule,
                strategy_configuration=self._strategy_configuration,
                risk_configuration=self._risk_configuration,
                cost_estimate=self._cost_estimate,
                authoritative_evidence=authoritative,
            )

    def validate_result_json(self, value: str | bytes | bytearray) -> CausalOrchestrationResult:
        decoded = json.loads(value)
        return self.validate_result(decoded)

    def _inject_failure(self, stage: str) -> None:
        if self._failure_injector is not None:
            self._failure_injector(stage)

    def advance(self) -> CausalOrchestrationResult | None:
        """Atomically consume one event and publish all-or-nothing causal effects."""
        with self._state.lock:
            event_position: int | None = None
            try:
                with self._state.scheduler_lease.transition() as transition:
                    event_position = transition.position_before
                    event = transition.event
                    self._inject_failure("after_event_inspection")
                    if event.payload_kind is not ReplayPayloadKind.MARKET_EVENT:
                        self._inject_failure("immediately_before_commit")
                        transition.commit()
                        self._inject_failure("during_commit_after_cursor")
                        return None
                    return self._evaluate_market_event(transition)
            except BaseException:
                if event_position is not None:
                    dict.pop(self._state.published_results, event_position, None)
                    dict.pop(self._state.authoritative_evidence, event_position, None)
                raise

    def _evaluate_market_event(
        self, transition: _LeasedSchedulerTransition
    ) -> CausalOrchestrationResult:
        event = transition.event
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
        self._inject_failure("during_visibility_resolution")
        released_market_events = self._released_prefix(transition.position_after)
        if not released_market_events or released_market_events[-1] != reference:
            raise OrchestrationInvariantError(
                "scheduler consumed prefix does not end with the triggering market event"
            )
        market_data = self._visible_slice(
            reference, bar, event.scheduled_at, released_market_events
        )
        self._inject_failure("during_indicator_calculation")
        indicators = _indicator_snapshot(market_data, self._strategy_configuration)
        manifest = self._artifact.manifest
        context = _strategy_evaluation_context(
            artifact=self._artifact,
            market=reference,
            market_data=market_data,
            indicators=indicators,
            cost_estimate=self._cost_estimate,
        )
        self._inject_failure("during_strategy_evaluation")
        decision = evaluate_strategy(context, self._strategy_configuration)
        if isinstance(decision, NoTradeDecision):
            built = self._build_result(
                transition=transition,
                reference=reference,
                released_market_events=released_market_events,
                market_data=market_data,
                indicators=indicators,
                decision=decision,
                risk_attempt=None,
                parent_before=None,
                allocation_before=None,
                parent_after=None,
                allocation_after=None,
                outcome=OrchestrationOutcome.NO_TRADE,
            )
            return self._publish_result(transition, *built)
        if decision.proposal.management_mandate.mandate_id != manifest.management_mandate_id:
            raise OrchestrationInvariantError(
                "proposal management mandate differs from run manifest"
            )
        self._inject_failure("during_risk_evaluation")
        state = self._coordinator.evaluation_state(manifest.account_id, manifest.allocation_id)
        preliminary = self._risk_engine.evaluate(
            decision.proposal,
            self._risk_configuration,
            state,
            evaluated_at=event.scheduled_at,
        )
        with self._coordinator.orchestration_transaction(
            decision.proposal,
            account_id=manifest.account_id,
            allocation_id=manifest.allocation_id,
        ):
            parent_before = self._coordinator.parent_snapshot(manifest.account_id)
            allocation_before = self._coordinator.allocation_snapshot(manifest.allocation_id)
            if preliminary.status is RiskDecisionStatus.REJECTED:
                risk_attempt = ReservationAttempt(
                    status=ReservationAttemptStatus.REJECTED,
                    risk_decision=preliminary,
                )
            else:
                self._inject_failure("during_sizing_allocation")
                risk_attempt = self._coordinator.reserve(
                    decision.proposal,
                    self._risk_configuration,
                    preliminary,
                    account_id=manifest.account_id,
                    allocation_id=manifest.allocation_id,
                    evaluated_at=event.scheduled_at,
                )
                self._inject_failure("after_reservation_mutation")
            self._inject_failure("during_capital_snapshot")
            parent_after = self._coordinator.parent_snapshot(manifest.account_id)
            allocation_after = self._coordinator.allocation_snapshot(manifest.allocation_id)
            outcome = (
                OrchestrationOutcome.CAPITAL_RESERVED
                if risk_attempt.status is ReservationAttemptStatus.RESERVED
                else OrchestrationOutcome.RISK_REJECTED
            )
            built = self._build_result(
                transition=transition,
                reference=reference,
                released_market_events=released_market_events,
                market_data=market_data,
                indicators=indicators,
                decision=decision,
                risk_attempt=risk_attempt,
                parent_before=parent_before,
                allocation_before=allocation_before,
                parent_after=parent_after,
                allocation_after=allocation_after,
                outcome=outcome,
            )
            return self._publish_result(transition, *built)

    def _publish_result(
        self,
        transition: _LeasedSchedulerTransition,
        result: CausalOrchestrationResult,
        authoritative_evidence: _AuthoritativeResultEvidence,
    ) -> CausalOrchestrationResult:
        position = transition.position_before
        if position in self._state.published_results:
            raise OrchestrationInvariantError(
                "scheduler position already has a published orchestration result"
            )
        self._inject_failure("immediately_before_commit")
        self._state.published_results[position] = result
        self._state.authoritative_evidence[position] = authoritative_evidence
        self._inject_failure("during_commit_after_result")
        transition.commit()
        self._inject_failure("during_commit_after_cursor")
        return result

    def _build_result(
        self,
        *,
        transition: _LeasedSchedulerTransition,
        reference: MarketEventReference,
        released_market_events: tuple[MarketEventReference, ...],
        market_data: MarketDataSlice,
        indicators: IndicatorSnapshot,
        decision: NoTradeDecision | TradeProposalDecision,
        risk_attempt: ReservationAttempt | None,
        parent_before: ParentCapitalSnapshot | None,
        allocation_before: AllocationSnapshot | None,
        parent_after: ParentCapitalSnapshot | None,
        allocation_after: AllocationSnapshot | None,
        outcome: OrchestrationOutcome,
    ) -> tuple[CausalOrchestrationResult, _AuthoritativeResultEvidence]:
        self._inject_failure("during_result_construction")
        authoritative_evidence = _AuthoritativeResultEvidence(
            indicators=indicators,
            strategy_decision=decision,
            risk_attempt=risk_attempt,
            parent_snapshot_before=parent_before,
            allocation_snapshot_before=allocation_before,
            parent_snapshot_after=parent_after,
            allocation_snapshot_after=allocation_after,
            outcome=outcome,
        )
        result = CausalOrchestrationResult._create_from_transition(
            artifact=self._artifact,
            dataset=self._dataset,
            schedule=self._state.scheduler_lease.schedule,
            strategy_configuration=self._strategy_configuration,
            risk_configuration=self._risk_configuration,
            cost_estimate=self._cost_estimate,
            authoritative_evidence=authoritative_evidence,
            scheduler_event_position=transition.position_before,
            scheduler_position_after=transition.position_after,
            triggering_event=transition.event,
            triggering_market_event=reference,
            released_market_events=released_market_events,
            market_data=market_data,
            indicators=indicators,
            strategy_decision=decision,
            risk_attempt=risk_attempt,
            parent_snapshot_after=parent_after,
            allocation_snapshot_after=allocation_after,
            outcome=outcome,
            evaluated_at=transition.event.scheduled_at,
        )
        self._inject_failure("during_result_validation")
        return result, authoritative_evidence

    def _visible_slice(
        self,
        reference: MarketEventReference,
        triggering_bar: HistoricalBar,
        as_of: datetime,
        released_market_events: tuple[MarketEventReference, ...],
    ) -> MarketDataSlice:
        result = _authoritative_market_slice(
            self._dataset,
            released_market_events,
            reference,
            as_of,
        )
        if triggering_bar not in result.bars:
            raise OrchestrationInvariantError("triggering bar is not causally visible")
        return result

    def _released_prefix(self, position: int) -> tuple[MarketEventReference, ...]:
        released: list[MarketEventReference] = []
        for event in self._state.scheduler_lease.schedule.events[:position]:
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
