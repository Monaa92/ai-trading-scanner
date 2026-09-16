"""Adversarial tests for the bounded Phase 6 causal orchestration step."""

from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Event

import pytest
from pydantic import ValidationError
from simulation_helpers import (
    cost_configuration,
    execution_configuration,
    execution_dimensions,
    initial_portfolio,
)
from strategy_helpers import strategy_bars, zeroish_costs

from ai_trading_scanner.domain import (
    AccountId,
    AgentId,
    AllocationId,
    ConfigurationVersionId,
    ManagementMandateId,
)
from ai_trading_scanner.domain.content_identity import canonical_json_bytes
from ai_trading_scanner.domain.execution import SubmissionMode
from ai_trading_scanner.indicators import (
    ATRConfig,
    EMAConfig,
    PriceBasis,
    ResetPolicy,
    RSIConfig,
    SmoothingMethod,
    VWAPConfig,
    calculate_indicator_configuration_id,
)
from ai_trading_scanner.market_data import (
    AdjustmentMethod,
    AvailabilityMode,
    CanonicalDataset,
    DataProvenance,
    HistoricalBar,
    QualityStatus,
)
from ai_trading_scanner.risk import (
    AllocationSnapshot,
    InMemoryCapitalCoordinator,
    LossStateScope,
    ParentCapitalSnapshot,
    ReservationAttemptStatus,
    RiskConfiguration,
    RiskRejectionCode,
    baseline_risk_configuration,
    calculate_reservation_id,
    calculate_risk_configuration_id,
    calculate_risk_decision_id,
    create_loss_state,
)
from ai_trading_scanner.simulation import (
    CashLedgerSnapshot,
    CausalOrchestrationResult,
    CausalOrchestrator,
    DeterministicReplayScheduler,
    MarketEventReference,
    OrchestrationInvariantError,
    OrchestrationOutcome,
    ReplayArtifactBundle,
    ReplayEvent,
    ReplayPhase,
    ResultFinalizationPayload,
    SchedulerExhaustedError,
    SchedulerLeaseError,
    SimulationResultStatus,
    SimulationRunManifest,
    calculate_marker_payload_id,
    calculate_market_event_id,
    calculate_orchestration_configuration_id,
    calculate_orchestration_result_id,
    calculate_replay_event_id,
    calculate_simulation_run_id,
)
from ai_trading_scanner.simulation.orchestration import _causal_parent_ids
from ai_trading_scanner.strategies import (
    BreakoutConfiguration,
    ManagementStyle,
    ManagementTrigger,
    MeanReversionConfiguration,
    MomentumConfiguration,
    MultiFactorConfiguration,
    NoTradeDecision,
    StrategyConfiguration,
    StrategyEvaluationContext,
    TradeProposalDecision,
    calculate_strategy_configuration_id,
    calculate_strategy_decision_id,
    create_management_mandate,
    evaluate_strategy,
)

AUTHORITY = ConfigurationVersionId.parse("phase6-orchestration-tests-v1")


def _dataset(bars: Sequence[HistoricalBar]) -> CanonicalDataset:
    frozen = tuple(bars)
    provenance = DataProvenance(
        provider="synthetic-test-fixture",
        source_dataset_id="phase6-orchestration",
        source_dataset_version="v1",
        timeframe=frozen[0].timeframe,
        source_timezone="America/New_York",
        requested_start_at=frozen[0].start_at,
        requested_end_at=frozen[-1].end_at,
        covered_start_at=frozen[0].start_at,
        covered_end_at=frozen[-1].end_at,
        ingested_at=datetime(2024, 12, 31, tzinfo=UTC),
        adjustment_method=AdjustmentMethod.RAW,
        availability_mode=AvailabilityMode.MODELED,
        modeled_publication_delay_seconds=5,
        calendar_version="exchange-calendars-4.13.2",
        normalization_version="test-v1",
        quality_status=QualityStatus.PASS,
    )
    return CanonicalDataset.create(provenance, frozen)


def _indicator_ids(configuration: StrategyConfiguration) -> tuple[object, ...]:
    configs = (
        EMAConfig(period=configuration.ema_fast_period),
        EMAConfig(period=configuration.ema_medium_period),
        EMAConfig(period=configuration.ema_slow_period),
        RSIConfig(period=configuration.rsi_period, smoothing=SmoothingMethod.WILDER),
        ATRConfig(period=configuration.atr_period, smoothing=SmoothingMethod.WILDER),
        VWAPConfig(price_basis=PriceBasis.TYPICAL_PRICE, reset_policy=ResetPolicy.SESSION),
    )
    return tuple(sorted((calculate_indicator_configuration_id(item) for item in configs), key=str))


def _multi_factor_mandate_id() -> ManagementMandateId:
    return create_management_mandate(
        ManagementStyle.MULTI_FACTOR_DYNAMIC,
        (
            ManagementTrigger.PROTECTIVE_STOP,
            ManagementTrigger.FACTORS_DETERIORATED,
            ManagementTrigger.THESIS_INVALIDATED,
        ),
    ).mandate_id


def _market_reference(dataset: CanonicalDataset, bar: HistoricalBar) -> MarketEventReference:
    content: dict[str, object] = {
        "schema_version": "market-event-reference-v1",
        "dataset_id": dataset.dataset_id,
        "instrument_id": bar.instrument_id,
        "interval_start_at": bar.start_at,
        "event_at": bar.end_at,
        "available_at": bar.available_at,
        "source_record_id": bar.source_record_id,
    }
    return MarketEventReference.model_validate(
        {"market_event_id": calculate_market_event_id(content), **content}
    )


def _event(run_id: object, at: datetime, phase: ReplayPhase, payload_id: object) -> ReplayEvent:
    kind = {
        ReplayPhase.PORTFOLIO_UPDATE: "PORTFOLIO_SNAPSHOT",
        ReplayPhase.MARKET_DATA_AVAILABLE: "MARKET_EVENT",
        ReplayPhase.RESULT_FINALIZATION: "RUN_RESULT",
    }[phase]
    content: dict[str, object] = {
        "schema_version": "replay-event-v1",
        "run_id": run_id,
        "scheduled_at": at,
        "phase": phase,
        "payload_kind": kind,
        "payload_id": str(payload_id),
    }
    return ReplayEvent.model_validate(
        {"replay_event_id": calculate_replay_event_id(content), **content}
    )


def _manifest(
    dataset: CanonicalDataset,
    configuration: StrategyConfiguration,
    risk: RiskConfiguration,
    *,
    suffix: str,
    submission_mode: SubmissionMode = SubmissionMode.ORDER_ENABLED,
    mandate_id: ManagementMandateId | None = None,
) -> SimulationRunManifest:
    execution = execution_configuration()
    costs = cost_configuration()
    dimensions = execution_dimensions(submission_mode=submission_mode)
    content: dict[str, object] = {
        "schema_version": "simulation-run-manifest-v1",
        "dataset_id": dataset.dataset_id,
        "account_id": AccountId.parse(f"account:orchestration-{suffix}"),
        "allocation_id": AllocationId.parse(f"allocation:orchestration-{suffix}"),
        "agent_id": AgentId.parse(f"agent:orchestration-{suffix}"),
        "strategy_id": configuration.strategy_id,
        "strategy_configuration_id": calculate_strategy_configuration_id(configuration),
        "strategy_version": configuration.strategy_version,
        "model_id": None,
        "indicator_configuration_ids": _indicator_ids(configuration),
        "risk_configuration_id": risk.risk_configuration_id,
        "management_mandate_id": mandate_id or ManagementMandateId.parse("mandate:test-only"),
        "configuration_version_id": AUTHORITY,
        "execution_model_id": execution.execution_model_id,
        "cost_model_id": costs.cost_model_id,
        "starting_capital": "1000",
        "reporting_currency": "USD",
        "execution_dimensions": dimensions,
        "random_seed": None,
    }
    return SimulationRunManifest.model_validate(
        {"run_id": calculate_simulation_run_id(content), **content}
    )


def _artifact(
    dataset: CanonicalDataset,
    manifest: SimulationRunManifest,
    *,
    shuffled: bool = False,
) -> ReplayArtifactBundle:
    portfolio = initial_portfolio(
        run_id=manifest.run_id,
        account_id=manifest.account_id,
        allocation_id=manifest.allocation_id,
        agent_id=manifest.agent_id,
        as_of=dataset.bars[0].start_at,
        starting_capital="1000",
        cash=CashLedgerSnapshot(
            currency="USD",
            available_cash=Decimal("1000"),
            reserved_cash=Decimal("0"),
            committed_cash=Decimal("0"),
            total_cash=Decimal("1000"),
        ),
        total_equity="1000",
    )
    references = tuple(_market_reference(dataset, bar) for bar in dataset.bars)
    finalization_content: dict[str, object] = {
        "schema_version": "result-finalization-payload-v1",
        "run_id": manifest.run_id,
        "status": SimulationResultStatus.INCOMPLETE,
        "final_portfolio_snapshot_id": portfolio.portfolio_snapshot_id,
        "realized_trade_result_ids": (),
        "finalized_at": dataset.bars[-1].available_at + timedelta(minutes=1),
    }
    finalization = ResultFinalizationPayload.model_validate(
        {
            "payload_id": calculate_marker_payload_id(finalization_content),
            **finalization_content,
        }
    )
    events = [
        _event(
            manifest.run_id,
            portfolio.as_of,
            ReplayPhase.PORTFOLIO_UPDATE,
            portfolio.portfolio_snapshot_id,
        ),
        *(
            _event(
                manifest.run_id,
                reference.available_at,
                ReplayPhase.MARKET_DATA_AVAILABLE,
                reference.market_event_id,
            )
            for reference in references
        ),
        _event(
            manifest.run_id,
            finalization.finalized_at,
            ReplayPhase.RESULT_FINALIZATION,
            finalization.payload_id,
        ),
    ]
    if shuffled:
        random.Random(71).shuffle(events)
        references = tuple(reversed(references))
    return ReplayArtifactBundle.create(
        manifest=manifest,
        events=tuple(events),
        market_events=references,
        portfolio_snapshots=(portfolio,),
        finalizations=(finalization,),
    )


def _coordinator(manifest: SimulationRunManifest) -> InMemoryCapitalCoordinator:
    parent = ParentCapitalSnapshot(
        account_id=manifest.account_id,
        currency="USD",
        total_capital=Decimal("1000"),
        available_capital=Decimal("1000"),
    )
    allocation = AllocationSnapshot(
        allocation_id=manifest.allocation_id,
        account_id=manifest.account_id,
        agent_id=manifest.agent_id,
        configuration_version_id=AUTHORITY,
        currency="USD",
        allocated_capital=Decimal("1000"),
        available_capital=Decimal("1000"),
    )
    first = datetime(2024, 7, 2, 13, 30, tzinfo=UTC)
    last = datetime(2024, 7, 2, 20, 0, tzinfo=UTC)
    parent_loss = create_loss_state(
        scope=LossStateScope.PARENT_ACCOUNT,
        account_id=manifest.account_id,
        session_id="XNYS:2024-07-02:exchange-calendars-4.13.2",
        session_start_at=first,
        session_end_at=last,
        observed_at=first,
        effective_at=first,
        valid_until=last,
        eligible_current_equity=Decimal("1000"),
        session_start_equity=Decimal("1000"),
        current_loss=Decimal("0"),
    )
    allocation_loss = create_loss_state(
        scope=LossStateScope.AGENT_ALLOCATION,
        account_id=manifest.account_id,
        allocation_id=manifest.allocation_id,
        agent_id=manifest.agent_id,
        session_id="XNYS:2024-07-02:exchange-calendars-4.13.2",
        session_start_at=first,
        session_end_at=last,
        observed_at=first,
        effective_at=first,
        valid_until=last,
        eligible_current_equity=Decimal("1000"),
        session_start_equity=Decimal("1000"),
        current_loss=Decimal("0"),
    )
    result = InMemoryCapitalCoordinator()
    result.register_parent(parent, parent_loss)
    result.register_allocation(allocation, allocation_loss)
    return result


def _risk(**changes: object) -> RiskConfiguration:
    base = baseline_risk_configuration(AUTHORITY)
    content = base.model_dump(mode="python", exclude={"risk_configuration_id"})
    content.update(changes)
    return RiskConfiguration(
        risk_configuration_id=calculate_risk_configuration_id(content), **content
    )


def _setup(
    suffix: str,
    *,
    configuration: StrategyConfiguration | None = None,
    bars: Sequence[HistoricalBar] | None = None,
    submission_mode: SubmissionMode = SubmissionMode.ORDER_ENABLED,
    risk: RiskConfiguration | None = None,
) -> tuple[
    CausalOrchestrator,
    ReplayArtifactBundle,
    CanonicalDataset,
    InMemoryCapitalCoordinator,
]:
    config = configuration or MultiFactorConfiguration()
    source_bars = tuple(bars or strategy_bars(["100"]))
    dataset = _dataset(source_bars)
    risk_config = risk or _risk()
    mandate = _multi_factor_mandate_id() if isinstance(config, MultiFactorConfiguration) else None
    manifest = _manifest(
        dataset,
        config,
        risk_config,
        suffix=suffix,
        submission_mode=submission_mode,
        mandate_id=mandate,
    )
    artifact = _artifact(dataset, manifest)
    coordinator = _coordinator(manifest)
    return (
        CausalOrchestrator(
            artifact=artifact,
            dataset=dataset,
            strategy_configuration=config,
            risk_configuration=risk_config,
            cost_estimate=zeroish_costs(),
            capital_coordinator=coordinator,
        ),
        artifact,
        dataset,
        coordinator,
    )


def _results(orchestrator: CausalOrchestrator) -> tuple[CausalOrchestrationResult, ...]:
    results: list[CausalOrchestrationResult] = []
    while orchestrator.scheduler.has_events:
        result = orchestrator.advance()
        if result is not None:
            results.append(result)
    return tuple(results)


def _trend_bars() -> tuple[HistoricalBar, ...]:
    closes = [str(Decimal("100") + Decimal(index) / Decimal("10")) for index in range(60)]
    return strategy_bars(closes)


def test_future_bar_in_artifact_is_invisible_until_its_event_is_consumed() -> None:
    orchestrator, _, dataset, _ = _setup("future", bars=strategy_bars(["100", "101"]))
    assert orchestrator.advance() is None
    first = orchestrator.advance()
    assert first is not None
    assert first.market_data.bars == (dataset.bars[0],)
    assert dataset.bars[1] not in first.market_data.bars
    second = orchestrator.advance()
    assert second is not None
    assert second.market_data.bars == dataset.bars


def test_strategy_cannot_reference_future_market_data() -> None:
    orchestrator, _, dataset, _ = _setup("future-forge", bars=strategy_bars(["100", "101"]))
    orchestrator.advance()
    result = orchestrator.advance()
    assert result is not None
    forged_slice = result.market_data.model_copy(
        update={
            "bars": dataset.bars,
            "content_hash_sha256": hashlib.sha256(canonical_json_bytes(dataset.bars)).hexdigest(),
        }
    )
    content = result.model_dump(mode="python")
    content["market_data"] = forged_slice
    with pytest.raises(ValidationError, match="unreleased data"):
        orchestrator.validate_result(content)


def test_current_released_bar_is_visible_and_is_the_trigger() -> None:
    orchestrator, _, dataset, _ = _setup("current")
    orchestrator.advance()
    result = orchestrator.advance()
    assert result is not None
    assert result.market_data.bars[-1] == dataset.bars[0]
    assert result.triggering_market_event == result.released_market_events[-1]


def test_shuffled_artifact_input_canonicalizes_to_same_artifact_and_schedule() -> None:
    config = MultiFactorConfiguration()
    dataset = _dataset(strategy_bars(["100", "101"]))
    risk = _risk()
    manifest = _manifest(
        dataset, config, risk, suffix="shuffle", mandate_id=_multi_factor_mandate_id()
    )
    ordered = _artifact(dataset, manifest)
    shuffled = _artifact(dataset, manifest, shuffled=True)
    assert ordered == shuffled
    assert ordered.artifact_id == shuffled.artifact_id


def test_repeated_content_identity_calculation_is_identical() -> None:
    orchestrator, _, _, _ = _setup("repeat")
    orchestrator.advance()
    result = orchestrator.advance()
    assert result is not None
    assert calculate_orchestration_result_id(result) == calculate_orchestration_result_id(result)
    assert orchestrator.validate_result_json(result.model_dump_json()) == result


def test_no_trade_is_first_class_and_skips_phase5_mutation() -> None:
    orchestrator, _, _, coordinator = _setup("no-trade")
    manifest = orchestrator.scheduler.run_id
    before = coordinator.allocation_snapshot(
        AllocationId.parse("allocation:orchestration-no-trade")
    )
    results = _results(orchestrator)
    result = results[0]
    assert isinstance(result.strategy_decision, NoTradeDecision)
    assert result.outcome is OrchestrationOutcome.NO_TRADE
    assert result.risk_attempt is None
    assert coordinator.allocation_snapshot(before.allocation_id) == before
    assert result.run_id == manifest


def test_valid_proposal_reaches_phase5_and_reserves_capital() -> None:
    orchestrator, _, _, _ = _setup("accepted", bars=_trend_bars())
    accepted = next(
        item
        for item in _results(orchestrator)
        if item.outcome is OrchestrationOutcome.CAPITAL_RESERVED
    )
    assert isinstance(accepted.strategy_decision, TradeProposalDecision)
    assert accepted.risk_attempt is not None
    assert accepted.risk_attempt.status is ReservationAttemptStatus.RESERVED
    assert accepted.risk_attempt.reservation is not None
    assert accepted.risk_attempt.risk_decision.sizing_decision is not None
    assert accepted.allocation_snapshot_after is not None
    assert accepted.allocation_snapshot_after.active_reservation_count == 1


def test_signal_only_proposal_produces_deterministic_risk_rejection() -> None:
    orchestrator, _, _, _ = _setup(
        "signal-only", bars=_trend_bars(), submission_mode=SubmissionMode.SIGNAL_ONLY
    )
    rejected = next(
        item
        for item in _results(orchestrator)
        if isinstance(item.strategy_decision, TradeProposalDecision)
    )
    assert rejected.outcome is OrchestrationOutcome.RISK_REJECTED
    assert rejected.risk_attempt is not None
    assert rejected.risk_attempt.risk_decision.reason_codes == (
        RiskRejectionCode.SUBMISSION_NOT_ENABLED,
    )


def test_risk_limit_rejection_retains_exact_phase5_evidence() -> None:
    restrictive = _risk(max_position_fraction=Decimal("0.00001"))
    orchestrator, _, _, _ = _setup("risk-reject", bars=_trend_bars(), risk=restrictive)
    rejected = next(
        item
        for item in _results(orchestrator)
        if isinstance(item.strategy_decision, TradeProposalDecision)
    )
    assert rejected.outcome is OrchestrationOutcome.RISK_REJECTED
    assert rejected.risk_attempt is not None
    assert RiskRejectionCode.POSITION_SIZE_EXCEEDED in (
        rejected.risk_attempt.risk_decision.reason_codes
    )


def test_wrong_run_evidence_is_rejected() -> None:
    orchestrator, _, _, _ = _setup("wrong-run")
    orchestrator.advance()
    result = orchestrator.advance()
    assert result is not None
    content = result.model_dump(mode="python")
    content["run_id"] = "sha256:" + "f" * 64
    with pytest.raises(ValidationError, match="scheduler and market evidence"):
        orchestrator.validate_result(content)


def test_wrong_agent_evidence_is_rejected() -> None:
    orchestrator, _, _, _ = _setup("wrong-agent")
    orchestrator.advance()
    result = orchestrator.advance()
    assert result is not None
    content = result.model_dump(mode="python")
    content["agent_id"] = "agent:foreign"
    with pytest.raises(ValidationError, match="visible causal evidence"):
        orchestrator.validate_result(content)


def test_foreign_allocation_is_rejected_before_scheduler_creation() -> None:
    config = MultiFactorConfiguration()
    dataset = _dataset(strategy_bars(["100"]))
    risk = _risk()
    manifest = _manifest(
        dataset, config, risk, suffix="foreign-allocation", mandate_id=_multi_factor_mandate_id()
    )
    artifact = _artifact(dataset, manifest)
    other_manifest = manifest.model_copy(
        update={"allocation_id": AllocationId.parse("allocation:foreign")}
    )
    with pytest.raises(OrchestrationInvariantError, match="allocation scope"):
        CausalOrchestrator(
            artifact=artifact,
            dataset=dataset,
            strategy_configuration=config,
            risk_configuration=risk,
            cost_estimate=zeroish_costs(),
            capital_coordinator=_coordinator(other_manifest),
        )


def test_unresolved_market_dependency_fails_closed() -> None:
    orchestrator, artifact, dataset, coordinator = _setup("unresolved")
    del orchestrator
    damaged = dataset.model_copy(update={"dataset_id": "sha256:" + "e" * 64})
    with pytest.raises(OrchestrationInvariantError, match="identity or quality"):
        CausalOrchestrator(
            artifact=artifact,
            dataset=damaged,
            strategy_configuration=MultiFactorConfiguration(),
            risk_configuration=_risk(),
            cost_estimate=zeroish_costs(),
            capital_coordinator=coordinator,
        )


def test_strategy_decision_cannot_claim_unseen_slice_hash() -> None:
    orchestrator, _, _, _ = _setup("unseen-hash")
    orchestrator.advance()
    result = orchestrator.advance()
    assert result is not None
    decision = result.strategy_decision.model_copy(
        update={"market_data_slice_hash_sha256": "f" * 64}
    )
    content = result.model_dump(mode="python")
    content["strategy_decision"] = decision
    with pytest.raises(ValidationError, match="strategy decision identity"):
        orchestrator.validate_result(content)


def test_four_strategies_receive_identical_normalized_information() -> None:
    results: list[CausalOrchestrationResult] = []
    configurations: tuple[StrategyConfiguration, ...] = (
        MomentumConfiguration(),
        MeanReversionConfiguration(),
        BreakoutConfiguration(),
        MultiFactorConfiguration(),
    )
    shared_bars = strategy_bars(["100"])
    for index, configuration in enumerate(configurations):
        orchestrator, _, _, _ = _setup(
            f"parity-{index}", configuration=configuration, bars=shared_bars
        )
        orchestrator.advance()
        result = orchestrator.advance()
        assert result is not None
        results.append(result)
    assert len({item.market_data.content_hash_sha256 for item in results}) == 1
    assert len({canonical_json_bytes(item.market_data.bars) for item in results}) == 1
    assert len({canonical_json_bytes(item.released_market_events) for item in results}) == 1


def test_multi_factor_receives_no_privileged_raw_information() -> None:
    momentum, _, _, _ = _setup("no-privilege-a", configuration=MomentumConfiguration())
    multi, _, _, _ = _setup("no-privilege-d", configuration=MultiFactorConfiguration())
    momentum.advance()
    multi.advance()
    momentum_result = momentum.advance()
    multi_result = multi.advance()
    assert momentum_result is not None and multi_result is not None
    assert momentum_result.market_data == multi_result.market_data
    assert momentum_result.released_market_events == multi_result.released_market_events


def test_orchestration_does_not_mutate_schedule_history() -> None:
    orchestrator, _, _, _ = _setup("history")
    before = orchestrator.scheduler.schedule
    _results(orchestrator)
    assert orchestrator.scheduler.schedule == before


def test_orchestration_consumes_each_event_once_and_then_exhausts() -> None:
    orchestrator, _, _, _ = _setup("once")
    events = orchestrator.scheduler.schedule.events
    _results(orchestrator)
    assert orchestrator.scheduler.position == len(events)
    assert len({event.replay_event_id for event in events}) == len(events)
    with pytest.raises(SchedulerExhaustedError):
        orchestrator.advance()


def test_duplicate_handles_share_consumed_market_visibility() -> None:
    first, artifact, dataset, coordinator = _setup("shared-handles")
    second = CausalOrchestrator(
        artifact=artifact,
        dataset=dataset,
        strategy_configuration=MultiFactorConfiguration(),
        risk_configuration=_risk(),
        cost_estimate=zeroish_costs(),
        capital_coordinator=coordinator,
    )
    assert first.advance() is None
    result = second.advance()
    assert result is not None
    assert first.released_market_events == second.released_market_events
    assert first.released_market_events == result.released_market_events
    assert first.advance() is None
    assert first.scheduler.exhausted


def test_configuration_identity_change_changes_orchestration_identity() -> None:
    first, artifact, _, _ = _setup("config-id")
    changed_risk = _risk(max_risk_fraction=Decimal("0.02"))
    first_id = calculate_orchestration_configuration_id(
        strategy_configuration=MultiFactorConfiguration(),
        risk_configuration=_risk(),
        cost_estimate=zeroish_costs(),
        artifact=artifact,
    )
    second_id = calculate_orchestration_configuration_id(
        strategy_configuration=MultiFactorConfiguration(),
        risk_configuration=changed_risk,
        cost_estimate=zeroish_costs(),
        artifact=artifact,
    )
    assert first_id != second_id
    assert first.scheduler.position == 0


def test_semantically_identical_result_reconstruction_is_byte_identical() -> None:
    orchestrator, _, _, _ = _setup("reconstruct")
    orchestrator.advance()
    result = orchestrator.advance()
    assert result is not None
    encoded = result.model_dump_json()
    reconstructed = orchestrator.validate_result_json(encoded)
    assert reconstructed.model_dump_json() == encoded
    assert reconstructed.orchestration_result_id == result.orchestration_result_id


def test_identical_timestamp_events_release_only_consumed_prefix() -> None:
    bars = list(strategy_bars(["100", "101"]))
    bars[0] = bars[0].model_copy(update={"available_at": bars[1].available_at})
    orchestrator, _, _, _ = _setup("same-time", bars=bars)
    orchestrator.advance()
    first = orchestrator.advance()
    second = orchestrator.advance()
    assert first is not None and second is not None
    assert first.evaluated_at == second.evaluated_at
    assert len(first.released_market_events) == 1
    assert len(first.market_data.bars) == 1
    assert len(second.released_market_events) == 2
    assert len(second.market_data.bars) == 2


def test_result_causal_parents_include_decision_risk_sizing_and_reservation() -> None:
    orchestrator, _, _, _ = _setup("parents", bars=_trend_bars())
    result = next(
        item
        for item in _results(orchestrator)
        if item.outcome is OrchestrationOutcome.CAPITAL_RESERVED
    )
    assert result.risk_attempt is not None
    risk = result.risk_attempt.risk_decision
    assert str(result.strategy_decision.decision_id) in result.causal_parent_ids
    assert str(risk.risk_decision_id) in result.causal_parent_ids
    assert risk.sizing_decision is not None
    assert str(risk.sizing_decision.sizing_decision_id) in result.causal_parent_ids
    assert result.risk_attempt.reservation is not None
    assert str(result.risk_attempt.reservation.reservation_id) in result.causal_parent_ids


def test_orchestrator_uses_only_simulation_without_network_or_wall_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError((args, kwargs))

    monkeypatch.setattr("socket.create_connection", forbidden)
    orchestrator, _, _, _ = _setup("offline")
    results = _results(orchestrator)
    assert len(results) == 1
    assert results[0].evaluated_at == results[0].triggering_event.scheduled_at


def test_same_input_repeats_identically_in_fresh_processes() -> None:
    test_path = Path(__file__).resolve()
    code = (
        "import importlib.util, json; "
        f"p={json.dumps(str(test_path))}; "
        "s=importlib.util.spec_from_file_location('orchestration_probe', p); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "o,_,_,_=m._setup('fresh-process', bars=m._trend_bars()); "
        "r=next(x for x in m._results(o) if x.outcome.value=='CAPITAL_RESERVED'); "
        "print(r.orchestration_result_id)"
    )
    first = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        cwd=test_path.parent,
    ).stdout.strip()
    second = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        cwd=test_path.parent,
    ).stdout.strip()
    assert first == second


def _fast_proposal_configuration() -> MultiFactorConfiguration:
    return MultiFactorConfiguration(
        ema_fast_period=1,
        ema_medium_period=2,
        ema_slow_period=3,
        rsi_period=2,
        atr_period=2,
        minimum_combined_score=Decimal("0.5"),
    )


def _fast_bars() -> tuple[HistoricalBar, ...]:
    return strategy_bars(("100", "100.1", "100.2", "100.3", "100.4", "100.5"))


def _advance_to_proposal_boundary(orchestrator: CausalOrchestrator) -> None:
    while orchestrator.scheduler.position < 3:
        orchestrator.advance()
    assert orchestrator.scheduler.position == 3


def _atomic_state(
    orchestrator: CausalOrchestrator,
    coordinator: InMemoryCapitalCoordinator,
) -> tuple[object, ...]:
    manifest = orchestrator.scheduler.schedule.run_id
    account_id = AccountId.parse(str(orchestrator._artifact.manifest.account_id))
    allocation_id = AllocationId.parse(str(orchestrator._artifact.manifest.allocation_id))
    return (
        manifest,
        orchestrator.scheduler.position,
        orchestrator.released_market_events,
        orchestrator.scheduler.published_result_ids,
        coordinator.parent_snapshot(account_id),
        coordinator.allocation_snapshot(allocation_id),
        tuple(sorted((str(key), value) for key, value in coordinator._reservations.items())),
        tuple(sorted((str(key), value) for key, value in coordinator._risk_decisions.items())),
    )


PROPOSAL_FAILURE_STAGES = (
    "after_event_inspection",
    "during_visibility_resolution",
    "during_indicator_calculation",
    "during_strategy_evaluation",
    "during_risk_evaluation",
    "during_sizing_allocation",
    "after_reservation_mutation",
    "during_capital_snapshot",
    "during_result_construction",
    "during_result_validation",
    "immediately_before_commit",
    "during_commit_after_result",
    "during_commit_after_cursor",
)


@pytest.mark.parametrize("stage", PROPOSAL_FAILURE_STAGES)
def test_proposal_transition_rolls_back_every_failure_boundary(stage: str) -> None:
    suffix = f"atomic-proposal-{stage.replace('_', '-')}"
    orchestrator, _, _, coordinator = _setup(
        suffix,
        configuration=_fast_proposal_configuration(),
        bars=_fast_bars(),
    )
    _advance_to_proposal_boundary(orchestrator)
    published_before = len(orchestrator.scheduler.published_result_ids)
    before = _atomic_state(orchestrator, coordinator)

    def fail_at(observed: str) -> None:
        if observed == stage:
            raise RuntimeError(f"injected failure: {stage}")

    orchestrator._failure_injector = fail_at
    with pytest.raises(RuntimeError, match="injected failure"):
        orchestrator.advance()
    assert _atomic_state(orchestrator, coordinator) == before

    orchestrator._failure_injector = None
    result = orchestrator.advance()
    assert result is not None
    assert result.scheduler_event_position == 3
    assert result.outcome is OrchestrationOutcome.CAPITAL_RESERVED
    assert orchestrator.scheduler.position == 4
    assert len(orchestrator.scheduler.published_result_ids) == published_before + 1
    assert coordinator.allocation_snapshot(result.allocation_id).active_reservation_count == 1


NO_TRADE_FAILURE_STAGES = (
    "after_event_inspection",
    "during_visibility_resolution",
    "during_indicator_calculation",
    "during_strategy_evaluation",
    "during_result_construction",
    "during_result_validation",
    "immediately_before_commit",
    "during_commit_after_result",
    "during_commit_after_cursor",
)


@pytest.mark.parametrize("stage", NO_TRADE_FAILURE_STAGES)
def test_no_trade_transition_rolls_back_every_reachable_failure_boundary(stage: str) -> None:
    suffix = f"atomic-no-trade-{stage.replace('_', '-')}"
    orchestrator, _, _, coordinator = _setup(suffix)
    assert orchestrator.advance() is None
    before = _atomic_state(orchestrator, coordinator)

    def fail_at(observed: str) -> None:
        if observed == stage:
            raise RuntimeError(f"injected failure: {stage}")

    orchestrator._failure_injector = fail_at
    with pytest.raises(RuntimeError, match="injected failure"):
        orchestrator.advance()
    assert _atomic_state(orchestrator, coordinator) == before

    orchestrator._failure_injector = None
    result = orchestrator.advance()
    assert result is not None
    assert result.outcome is OrchestrationOutcome.NO_TRADE
    assert orchestrator.scheduler.position == 2
    assert len(orchestrator.scheduler.published_result_ids) == 1


def _setup_with_retained_scheduler(
    suffix: str,
) -> tuple[DeterministicReplayScheduler, CausalOrchestrator]:
    configuration = MultiFactorConfiguration()
    dataset = _dataset(strategy_bars(("100", "101")))
    risk = _risk()
    manifest = _manifest(
        dataset,
        configuration,
        risk,
        suffix=suffix,
        mandate_id=_multi_factor_mandate_id(),
    )
    artifact = _artifact(dataset, manifest)
    coordinator = _coordinator(manifest)
    retained = DeterministicReplayScheduler.from_artifact(artifact)
    orchestrator = CausalOrchestrator(
        artifact=artifact,
        dataset=dataset,
        strategy_configuration=configuration,
        risk_configuration=risk,
        cost_estimate=zeroish_costs(),
        capital_coordinator=coordinator,
    )
    return retained, orchestrator


def test_public_scheduler_view_cannot_advance_authoritative_cursor() -> None:
    orchestrator, _, _, _ = _setup("public-view-attack")
    before = orchestrator.scheduler.position
    with pytest.raises(AttributeError):
        orchestrator.scheduler.next_event()  # type: ignore[attr-defined]
    assert orchestrator.scheduler.position == before


def test_retained_and_second_scheduler_handles_fail_closed_after_lease() -> None:
    retained, orchestrator = _setup_with_retained_scheduler("retained-handle-attack")
    second = DeterministicReplayScheduler.from_artifact(orchestrator._artifact)
    before = orchestrator.scheduler.position
    for handle in (retained, second):
        with pytest.raises(SchedulerLeaseError, match="exclusively leased"):
            handle.next_event()
        assert orchestrator.scheduler.position == before


def test_external_handle_cannot_consume_first_market_event() -> None:
    retained, orchestrator = _setup_with_retained_scheduler("first-market-attack")
    assert orchestrator.advance() is None
    before = orchestrator.scheduler.position
    with pytest.raises(SchedulerLeaseError, match="exclusively leased"):
        retained.next_event()
    assert orchestrator.scheduler.position == before
    result = orchestrator.advance()
    assert result is not None
    assert result.scheduler_event_position == before


def test_concurrent_external_advance_fails_closed_without_skipping() -> None:
    retained, orchestrator = _setup_with_retained_scheduler("concurrent-external-attack")
    assert orchestrator.advance() is None
    entered = Event()
    release = Event()

    def block_at_visibility(stage: str) -> None:
        if stage == "during_visibility_resolution":
            entered.set()
            assert release.wait(timeout=10)

    orchestrator._failure_injector = block_at_visibility
    with ThreadPoolExecutor(max_workers=2) as pool:
        orchestration_future = pool.submit(orchestrator.advance)
        assert entered.wait(timeout=10)
        external_future = pool.submit(retained.next_event)
        release.set()
        result = orchestration_future.result(timeout=10)
        with pytest.raises(SchedulerLeaseError, match="exclusively leased"):
            external_future.result(timeout=10)
    orchestrator._failure_injector = None
    assert result is not None
    assert result.scheduler_event_position == 1
    assert orchestrator.scheduler.position == 2


def test_concurrent_orchestrators_publish_distinct_events_once() -> None:
    first, artifact, dataset, coordinator = _setup(
        "concurrent-orchestrators", bars=strategy_bars(("100", "101"))
    )
    second = CausalOrchestrator(
        artifact=artifact,
        dataset=dataset,
        strategy_configuration=MultiFactorConfiguration(),
        risk_configuration=_risk(),
        cost_estimate=zeroish_costs(),
        capital_coordinator=coordinator,
    )
    assert first.advance() is None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            future.result(timeout=10)
            for future in (pool.submit(first.advance), pool.submit(second.advance))
        )
    assert all(result is not None for result in results)
    positions = {result.scheduler_event_position for result in results if result is not None}
    assert positions == {1, 2}
    assert first.scheduler.position == 3
    assert len(set(first.scheduler.published_result_ids)) == 2


def _reidentify_result(content: dict[str, object]) -> dict[str, object]:
    content["causal_parent_ids"] = _causal_parent_ids(content)
    content["orchestration_result_id"] = calculate_orchestration_result_id(content)
    return content


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("artifact_id", "sha256:" + "a" * 64),
        ("schedule_id", "sha256:" + "b" * 64),
        ("scheduler_event_position", 2),
        ("run_id", "sha256:" + "c" * 64),
        ("orchestration_configuration_id", "sha256:" + "d" * 64),
        ("strategy_configuration_id", "sha256:" + "e" * 64),
        ("cost_methodology_version_id", "cost-methodology:foreign"),
    ),
)
def test_context_bound_validation_rejects_rehashed_provenance_tampering(
    field: str, replacement: object
) -> None:
    orchestrator, _, _, _ = _setup(
        f"provenance-{field.replace('_', '-')}",
        configuration=_fast_proposal_configuration(),
        bars=_fast_bars(),
    )
    _advance_to_proposal_boundary(orchestrator)
    result = orchestrator.advance()
    assert result is not None
    content = result.model_dump(mode="python")
    content[field] = replacement
    _reidentify_result(content)
    with pytest.raises(ValidationError):
        orchestrator.validate_result(content)


def test_context_bound_validation_rejects_wrong_rehashed_event_and_prefix() -> None:
    orchestrator, _, _, _ = _setup(
        "provenance-event-prefix",
        configuration=_fast_proposal_configuration(),
        bars=_fast_bars(),
    )
    _advance_to_proposal_boundary(orchestrator)
    result = orchestrator.advance()
    assert result is not None

    wrong_event = result.model_dump(mode="python")
    wrong_event["triggering_event"] = orchestrator.scheduler.schedule.events[2]
    _reidentify_result(wrong_event)
    with pytest.raises(ValidationError, match="triggering scheduler"):
        orchestrator.validate_result(wrong_event)

    wrong_prefix = result.model_dump(mode="python")
    wrong_prefix["released_market_events"] = result.released_market_events[1:]
    _reidentify_result(wrong_prefix)
    with pytest.raises(ValidationError, match="exact consumed schedule prefix"):
        orchestrator.validate_result(wrong_prefix)


def test_generic_result_reconstruction_without_authoritative_context_is_rejected() -> None:
    orchestrator, _, _, _ = _setup("provenance-context-required")
    assert orchestrator.advance() is None
    result = orchestrator.advance()
    assert result is not None
    with pytest.raises(ValidationError, match="authoritative orchestration context"):
        CausalOrchestrationResult.model_validate(result.model_dump(mode="python"))
    with pytest.raises(ValidationError, match="authoritative orchestration context"):
        CausalOrchestrationResult.model_validate(result)
    assert orchestrator.validate_result(result) == result
    assert orchestrator.validate_result_json(result.model_dump_json()) == result


def _accepted_orchestration_result(
    suffix: str,
) -> tuple[CausalOrchestrator, CausalOrchestrationResult]:
    orchestrator, _, _, _ = _setup(
        suffix,
        configuration=_fast_proposal_configuration(),
        bars=_fast_bars(),
    )
    _advance_to_proposal_boundary(orchestrator)
    result = orchestrator.advance()
    assert result is not None
    assert result.outcome is OrchestrationOutcome.CAPITAL_RESERVED
    return orchestrator, result


def _change_latest_indicator(
    result: CausalOrchestrationResult,
    field: str,
    value: Decimal,
) -> dict[str, object]:
    series = getattr(result.indicators, field)
    changed_point = series.points[-1].model_copy(update={"value": value})
    changed_series = series.model_copy(update={"points": (*series.points[:-1], changed_point)})
    changed_indicators = result.indicators.model_copy(update={field: changed_series})
    content = result.model_dump(mode="python")
    content["indicators"] = changed_indicators
    return _reidentify_result(content)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ema_fast", Decimal("200.2")),
        ("rsi", Decimal("12.345")),
        ("atr", Decimal("99.999")),
        ("session_vwap", Decimal("300.3")),
    ),
)
def test_reidentified_indicator_fabrication_fails_authoritative_recomputation(
    field: str, value: Decimal
) -> None:
    orchestrator, result = _accepted_orchestration_result(f"forged-{field}")
    if field == "ema_fast":
        assert result.indicators.ema_fast.points[-1].value == Decimal("100.2")
    forged = _change_latest_indicator(result, field, value)
    with pytest.raises(ValidationError, match="indicator evidence"):
        orchestrator.validate_result(forged)


def test_reidentified_valid_looking_strategy_decision_substitution_is_rejected() -> None:
    orchestrator, result = _accepted_orchestration_result("forged-decision")
    changed = result.strategy_decision.model_copy(update={"detail": "fabricated detail"})
    changed = changed.model_copy(update={"decision_id": calculate_strategy_decision_id(changed)})
    content = result.model_dump(mode="python")
    content["strategy_decision"] = changed
    _reidentify_result(content)
    with pytest.raises(ValidationError, match="strategy decision"):
        orchestrator.validate_result(content)


def test_reidentified_zero_reservation_post_snapshots_are_rejected() -> None:
    orchestrator, result = _accepted_orchestration_result("forged-zero-post")
    assert result.risk_attempt is not None
    before = result.risk_attempt.risk_decision.source_evaluation_state
    content = result.model_dump(mode="python")
    content["parent_snapshot_after"] = before.parent
    content["allocation_snapshot_after"] = before.allocation
    _reidentify_result(content)
    with pytest.raises(ValidationError, match="authoritative transaction"):
        orchestrator.validate_result(content)


def test_reidentified_reserved_amount_inconsistent_with_sizing_is_rejected() -> None:
    orchestrator, result = _accepted_orchestration_result("forged-reserved-amount")
    assert result.risk_attempt is not None and result.risk_attempt.reservation is not None
    assert result.risk_attempt.risk_decision.sizing_decision is not None
    assert result.risk_attempt.reservation.reserved_amount == Decimal("963.768273168")
    changed = result.risk_attempt.reservation.model_copy(update={"reserved_amount": Decimal("1")})
    changed = changed.model_copy(update={"reservation_id": calculate_reservation_id(changed)})
    attempt = result.risk_attempt.model_copy(update={"reservation": changed})
    content = result.model_dump(mode="python")
    content["risk_attempt"] = attempt
    _reidentify_result(content)
    with pytest.raises(ValidationError, match="authoritative transaction"):
        orchestrator.validate_result(content)


def test_reidentified_valid_looking_reservation_identity_is_rejected() -> None:
    orchestrator, result = _accepted_orchestration_result("forged-reservation-id")
    assert result.risk_attempt is not None and result.risk_attempt.reservation is not None
    changed = result.risk_attempt.reservation.model_copy(
        update={"expires_at": result.risk_attempt.reservation.expires_at + timedelta(seconds=1)}
    )
    changed = changed.model_copy(update={"reservation_id": calculate_reservation_id(changed)})
    attempt = result.risk_attempt.model_copy(update={"reservation": changed})
    content = result.model_dump(mode="python")
    content["risk_attempt"] = attempt
    _reidentify_result(content)
    with pytest.raises(ValidationError, match="authoritative transaction"):
        orchestrator.validate_result(content)


def test_reidentified_post_transaction_revisions_are_rejected() -> None:
    orchestrator, result = _accepted_orchestration_result("forged-revisions")
    assert result.parent_snapshot_after is not None
    assert result.allocation_snapshot_after is not None
    content = result.model_dump(mode="python")
    content["parent_snapshot_after"] = result.parent_snapshot_after.model_copy(
        update={"revision": result.parent_snapshot_after.revision + 1}
    )
    content["allocation_snapshot_after"] = result.allocation_snapshot_after.model_copy(
        update={"revision": result.allocation_snapshot_after.revision + 1}
    )
    _reidentify_result(content)
    with pytest.raises(ValidationError, match="authoritative transaction"):
        orchestrator.validate_result(content)


def test_reidentified_foreign_phase5_evidence_is_rejected() -> None:
    orchestrator, result = _accepted_orchestration_result("foreign-phase5-local")
    _, foreign = _accepted_orchestration_result("foreign-phase5-other")
    content = result.model_dump(mode="python")
    content.update(
        {
            "risk_attempt": foreign.risk_attempt,
            "parent_snapshot_after": foreign.parent_snapshot_after,
            "allocation_snapshot_after": foreign.allocation_snapshot_after,
            "outcome": foreign.outcome,
        }
    )
    _reidentify_result(content)
    with pytest.raises(ValidationError):
        orchestrator.validate_result(content)


def test_reidentified_accepted_status_change_is_rejected() -> None:
    orchestrator, result = _accepted_orchestration_result("forged-status")
    content = result.model_dump(mode="python")
    content["outcome"] = OrchestrationOutcome.RISK_REJECTED
    _reidentify_result(content)
    with pytest.raises(ValidationError, match="authoritative transaction"):
        orchestrator.validate_result(content)


def test_reidentified_rejection_reasons_are_rejected() -> None:
    restrictive = _risk(max_position_fraction=Decimal("0.00001"))
    orchestrator, _, _, _ = _setup("forged-rejection-reasons", bars=_trend_bars(), risk=restrictive)
    result = next(
        item
        for item in _results(orchestrator)
        if item.outcome is OrchestrationOutcome.RISK_REJECTED
    )
    assert result.risk_attempt is not None
    changed_risk = result.risk_attempt.risk_decision.model_copy(
        update={"reason_codes": (RiskRejectionCode.TRADING_LOCK,)}
    )
    changed_risk = changed_risk.model_copy(
        update={"risk_decision_id": calculate_risk_decision_id(changed_risk)}
    )
    changed_attempt = result.risk_attempt.model_copy(update={"risk_decision": changed_risk})
    content = result.model_dump(mode="python")
    content["risk_attempt"] = changed_attempt
    _reidentify_result(content)
    with pytest.raises(ValidationError, match="authoritative transaction"):
        orchestrator.validate_result(content)


@pytest.mark.parametrize("kind", ("NO_TRADE", "RISK_REJECTED", "CAPITAL_RESERVED"))
def test_legitimate_outcome_reconstruction_remains_deterministic(kind: str) -> None:
    if kind == "NO_TRADE":
        orchestrator, _, _, _ = _setup("valid-rebuild-no-trade")
        assert orchestrator.advance() is None
        result = orchestrator.advance()
    elif kind == "RISK_REJECTED":
        orchestrator, _, _, _ = _setup(
            "valid-rebuild-rejected",
            bars=_trend_bars(),
            risk=_risk(max_position_fraction=Decimal("0.00001")),
        )
        result = next(
            item
            for item in _results(orchestrator)
            if item.outcome is OrchestrationOutcome.RISK_REJECTED
        )
    else:
        orchestrator, result = _accepted_orchestration_result("valid-rebuild-reserved")
    assert result is not None
    assert orchestrator.validate_result_json(result.model_dump_json()) == result


def test_normal_advance_evaluates_strategy_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    original = evaluate_strategy

    def counted(
        context: StrategyEvaluationContext,
        configuration: StrategyConfiguration,
    ) -> NoTradeDecision | TradeProposalDecision:
        nonlocal calls
        calls += 1
        return original(context, configuration)

    monkeypatch.setattr("ai_trading_scanner.simulation.orchestration.evaluate_strategy", counted)
    orchestrator, _, _, _ = _setup("single-evaluation")
    assert orchestrator.advance() is None
    assert orchestrator.advance() is not None
    assert calls == 1
