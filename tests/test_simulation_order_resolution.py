"""Behavioral and adversarial tests for Phase 6.1 order/terminal resolution."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from simulation_helpers import cost_configuration, execution_configuration, execution_dimensions
from strategy_helpers import zeroish_costs
from test_simulation_orchestration import (
    AUTHORITY,
    _advance_to_proposal_boundary,
    _artifact,
    _coordinator,
    _fast_bars,
    _fast_proposal_configuration,
    _indicator_ids,
    _multi_factor_mandate_id,
    _risk,
    _setup,
)

from ai_trading_scanner.domain import AccountId, AgentId, AllocationId, SimulatedOrderId
from ai_trading_scanner.market_data import (
    AdjustmentMethod,
    AvailabilityMode,
    CanonicalDataset,
    DataProvenance,
    HistoricalBar,
    QualityStatus,
    UsEquitiesCalendar,
)
from ai_trading_scanner.risk import InMemoryCapitalCoordinator
from ai_trading_scanner.simulation import (
    CausalOrchestrationResult,
    CausalOrchestrator,
    ExecutionResolutionOutcome,
    ExecutionResolutionReason,
    LiquidityResolutionOutcome,
    OrderCreationCommand,
    OrderCreationOutcome,
    OrderCreationReceipt,
    OrderProjectionNotFoundError,
    OrderResolutionInvariantError,
    OrderTerminalResolver,
    SimulatedOrderProjection,
    SimulatedOrderProjectionState,
    SimulationExecutionConfiguration,
    SimulationLiquidityConfiguration,
    SimulationRunManifest,
    calculate_liquidity_model_id,
    calculate_order_creation_command_id,
    calculate_simulation_run_id,
    serialize_order_terminal_resolution,
)
from ai_trading_scanner.strategies import (
    MultiFactorConfiguration,
    calculate_strategy_configuration_id,
)


def _liquidity(participation: str = "0.10") -> SimulationLiquidityConfiguration:
    content: dict[str, object] = {
        "schema_version": "simulation-liquidity-v1",
        "model_version": "reported-bar-volume-cap-v1",
        "maximum_bar_volume_participation": participation,
        "zero_volume_policy": "REJECT_FULL_FILL",
        "partial_fills_supported": False,
    }
    return SimulationLiquidityConfiguration.model_validate(
        {"liquidity_model_id": calculate_liquidity_model_id(content), **content}
    )


def _dataset_without_coverage(bars: tuple[HistoricalBar, ...]) -> CanonicalDataset:
    provenance = DataProvenance(
        provider="synthetic-order-resolution",
        source_dataset_id="phase6.1",
        source_dataset_version="v1",
        timeframe=bars[0].timeframe,
        source_timezone="America/New_York",
        ingested_at=datetime(2024, 12, 31, tzinfo=UTC),
        adjustment_method=AdjustmentMethod.RAW,
        availability_mode=AvailabilityMode.MODELED,
        modeled_publication_delay_seconds=5,
        calendar_version="exchange-calendars-4.13.2",
        normalization_version="phase6.1-test-v1",
        quality_status=QualityStatus.PASS,
    )
    return CanonicalDataset.create(provenance, bars)


def _custom_environment(
    suffix: str,
    *,
    dataset: CanonicalDataset,
    execution: SimulationExecutionConfiguration,
    participation: str = "0.10",
    proposal_validity_intervals: int = 2,
) -> tuple[
    CausalOrchestrator,
    CausalOrchestrationResult,
    OrderTerminalResolver,
    OrderCreationReceipt,
]:
    configuration_content = _fast_proposal_configuration().model_dump(mode="python")
    configuration_content["proposal_validity_intervals"] = proposal_validity_intervals
    configuration = MultiFactorConfiguration.model_validate(configuration_content)
    risk = _risk()
    costs = cost_configuration()
    manifest_content: dict[str, object] = {
        "schema_version": "simulation-run-manifest-v1",
        "dataset_id": dataset.dataset_id,
        "account_id": AccountId.parse(f"account:order-resolution-{suffix}"),
        "allocation_id": AllocationId.parse(f"allocation:order-resolution-{suffix}"),
        "agent_id": AgentId.parse(f"agent:order-resolution-{suffix}"),
        "strategy_id": configuration.strategy_id,
        "strategy_configuration_id": calculate_strategy_configuration_id(configuration),
        "strategy_version": configuration.strategy_version,
        "model_id": None,
        "indicator_configuration_ids": _indicator_ids(configuration),
        "risk_configuration_id": risk.risk_configuration_id,
        "management_mandate_id": _multi_factor_mandate_id(),
        "configuration_version_id": AUTHORITY,
        "execution_model_id": execution.execution_model_id,
        "cost_model_id": costs.cost_model_id,
        "starting_capital": "1000",
        "reporting_currency": "USD",
        "execution_dimensions": execution_dimensions(),
        "random_seed": None,
    }
    manifest = SimulationRunManifest.model_validate(
        {"run_id": calculate_simulation_run_id(manifest_content), **manifest_content}
    )
    artifact = _artifact(dataset, manifest)
    coordinator: InMemoryCapitalCoordinator = _coordinator(manifest)
    orchestrator = CausalOrchestrator(
        artifact=artifact,
        dataset=dataset,
        strategy_configuration=configuration,
        risk_configuration=risk,
        cost_estimate=zeroish_costs(),
        capital_coordinator=coordinator,
    )
    _advance_to_proposal_boundary(orchestrator)
    result = orchestrator.advance()
    assert result is not None
    liquidity = _liquidity(participation)
    resolver = OrderTerminalResolver(
        artifact=artifact,
        dataset=dataset,
        orchestrator=orchestrator,
        execution_configuration=execution,
        liquidity_configuration=liquidity,
    )
    command = OrderCreationCommand.create(result, execution, liquidity)
    receipt = resolver.create_order(command, result)
    return orchestrator, result, resolver, receipt


def _environment(
    suffix: str,
    *,
    participation: str = "0.10",
    failure_stage: str | None = None,
) -> tuple[
    CausalOrchestrator,
    CausalOrchestrationResult,
    OrderTerminalResolver,
    OrderCreationCommand,
]:
    orchestrator, artifact, dataset, _ = _setup(
        f"order-resolution-{suffix}",
        configuration=_fast_proposal_configuration(),
        bars=_fast_bars(),
    )
    _advance_to_proposal_boundary(orchestrator)
    result = orchestrator.advance()
    assert result is not None
    liquidity = _liquidity(participation)

    def inject(stage: str) -> None:
        if stage == failure_stage:
            raise RuntimeError(f"injected:{stage}")

    resolver = OrderTerminalResolver(
        artifact=artifact,
        dataset=dataset,
        orchestrator=orchestrator,
        execution_configuration=execution_configuration(),
        liquidity_configuration=liquidity,
        failure_injector=inject if failure_stage is not None else None,
    )
    command = OrderCreationCommand.create(result, execution_configuration(), liquidity)
    return orchestrator, result, resolver, command


def _created(
    suffix: str,
    *,
    participation: str = "0.10",
    failure_stage: str | None = None,
) -> tuple[
    CausalOrchestrator,
    CausalOrchestrationResult,
    OrderTerminalResolver,
    OrderCreationReceipt,
]:
    orchestrator, result, resolver, command = _environment(
        suffix, participation=participation, failure_stage=failure_stage
    )
    receipt = resolver.create_order(command, result)
    assert receipt.outcome is OrderCreationOutcome.CREATED
    assert receipt.order_id is not None
    return orchestrator, result, resolver, receipt


def _advance_to_terminal(
    orchestrator: CausalOrchestrator,
    resolver: OrderTerminalResolver,
    order_id: SimulatedOrderId,
) -> SimulatedOrderProjection:
    while True:
        projection = resolver.resolve(order_id)
        if projection.terminal_resolution is not None:
            return projection
        if not orchestrator.scheduler.has_events:
            raise AssertionError("exhausted without terminal resolution")
        orchestrator.advance()


def test_order_creation_is_idempotent_and_does_not_duplicate_projection() -> None:
    _, result, resolver, command = _environment("idempotent-create")
    first = resolver.create_order(command, result)
    second = resolver.create_order(command, result)
    assert first is second
    assert first.outcome is OrderCreationOutcome.CREATED
    assert first.order_id is not None
    assert resolver.projection(first.order_id).revision == 1


def test_concurrent_duplicate_creation_returns_one_order_identity() -> None:
    _, result, resolver, command = _environment("concurrent-create")
    with ThreadPoolExecutor(max_workers=8) as pool:
        receipts = tuple(pool.map(lambda _: resolver.create_order(command, result), range(16)))
    assert len({item.receipt_id for item in receipts}) == 1
    assert len({item.order_id for item in receipts}) == 1


def test_unreleased_future_bar_cannot_resolve_order() -> None:
    orchestrator, _, resolver, receipt = _created("future-hidden")
    assert receipt.order_id is not None
    initial = resolver.resolve(receipt.order_id)
    assert initial.state is SimulatedOrderProjectionState.CREATED
    assert initial.terminal_resolution is None
    orchestrator.advance()
    after_one = resolver.resolve(receipt.order_id)
    assert after_one.terminal_resolution is None


def test_first_released_strictly_later_bar_produces_fill_ready_only() -> None:
    orchestrator, _, resolver, receipt = _created("fill-ready")
    assert receipt.order_id is not None
    projection = _advance_to_terminal(orchestrator, resolver, receipt.order_id)
    terminal = projection.terminal_resolution
    assert terminal is not None
    assert projection.state is SimulatedOrderProjectionState.FILL_READY
    assert terminal.payload.outcome is ExecutionResolutionOutcome.FILL_READY
    assert terminal.payload.reason is None
    assert terminal.liquidity_outcome is LiquidityResolutionOutcome.FULL_FILL_AVAILABLE
    assert terminal.payload.source_market_event_id in terminal.released_market_event_ids
    assert terminal.payload.source_market_event_id in terminal.candidate_market_event_ids


def test_bar_open_equal_to_eligibility_is_excluded_deterministically() -> None:
    execution = execution_configuration(routing_latency_seconds=295)
    dataset = _dataset_without_coverage(_fast_bars())
    orchestrator, _, resolver, receipt = _custom_environment(
        "equal-eligibility",
        dataset=dataset,
        execution=execution,
        proposal_validity_intervals=4,
    )
    assert receipt.order_id is not None
    projection = _advance_to_terminal(orchestrator, resolver, receipt.order_id)
    terminal = projection.terminal_resolution
    assert terminal is not None
    assert terminal.payload.outcome is ExecutionResolutionOutcome.FILL_READY
    source = terminal.payload.source_market_event_id
    references = tuple(orchestrator.released_market_events)
    equal_bar = dataset.bars[4]
    selected_bar = dataset.bars[5]
    equal_reference = next(
        item for item in references if item.interval_start_at == equal_bar.start_at
    )
    selected_reference = next(
        item for item in references if item.interval_start_at == selected_bar.start_at
    )
    assert resolver.projection(receipt.order_id).order.eligible_at == equal_bar.start_at
    assert source != equal_reference.market_event_id
    assert source == selected_reference.market_event_id


def test_eligibility_equal_to_expiry_rejects_before_order_creation() -> None:
    execution = execution_configuration(routing_latency_seconds=295)
    dataset = _dataset_without_coverage(_fast_bars())
    _, _, _, receipt = _custom_environment(
        "eligibility-equals-expiry",
        dataset=dataset,
        execution=execution,
        proposal_validity_intervals=1,
    )
    assert receipt.outcome is OrderCreationOutcome.REJECTED
    assert receipt.rejection_reason is not None
    assert receipt.rejection_reason.value == "ELIGIBILITY_NOT_BEFORE_EXPIRY"
    assert receipt.order_id is None
    assert receipt.projection_id is None


def test_missing_eligible_bars_expire_without_synthesis() -> None:
    dataset = _dataset_without_coverage(_fast_bars()[:3])
    orchestrator, _, resolver, receipt = _custom_environment(
        "missing-expiry",
        dataset=dataset,
        execution=execution_configuration(),
    )
    assert receipt.order_id is not None
    projection = _advance_to_terminal(orchestrator, resolver, receipt.order_id)
    terminal = projection.terminal_resolution
    assert terminal is not None
    assert projection.state is SimulatedOrderProjectionState.EXPIRED_UNFILLED
    assert terminal.payload.outcome is ExecutionResolutionOutcome.EXPIRED_UNFILLED
    assert terminal.payload.reason is ExecutionResolutionReason.ORDER_VALIDITY_EXPIRED
    assert terminal.candidate_market_event_ids == ()


def test_next_session_bar_never_fills_intraday_order() -> None:
    source = _fast_bars()[:3]
    next_session = UsEquitiesCalendar().session_for_date(date(2024, 7, 3))
    assert next_session is not None
    next_template = _fast_bars()[3]
    next_content = next_template.model_dump(mode="python")
    next_content.update(
        {
            "session_id": next_session.session_id,
            "start_at": next_session.open_at,
            "end_at": next_session.open_at + next_template.timeframe.duration,
            "available_at": (
                next_session.open_at + next_template.timeframe.duration + timedelta(seconds=5)
            ),
            "source_record_id": "phase6.1:next-session",
        }
    )
    next_bar = HistoricalBar.model_validate(next_content)
    dataset = _dataset_without_coverage((*source, next_bar))
    orchestrator, _, resolver, receipt = _custom_environment(
        "next-session",
        dataset=dataset,
        execution=execution_configuration(),
        proposal_validity_intervals=100,
    )
    assert receipt.order_id is not None
    projection = _advance_to_terminal(orchestrator, resolver, receipt.order_id)
    terminal = projection.terminal_resolution
    assert terminal is not None
    assert projection.state is SimulatedOrderProjectionState.NO_ELIGIBLE_DATA
    assert terminal.payload.outcome is ExecutionResolutionOutcome.NO_ELIGIBLE_DATA
    assert terminal.payload.reason is ExecutionResolutionReason.NO_ELIGIBLE_SAME_SESSION_BAR
    next_reference = next(
        item
        for item in orchestrator.released_market_events
        if item.interval_start_at == next_bar.start_at
    )
    assert next_reference.market_event_id not in terminal.candidate_market_event_ids


def test_same_session_gap_uses_first_actual_released_open_without_synthesis() -> None:
    source = list(_fast_bars())
    gap_content = source[4].model_dump(mode="python")
    gap_content.update(
        {
            "open": Decimal("125"),
            "high": Decimal("126"),
            "low": Decimal("124"),
            "close": Decimal("125.5"),
            "source_record_id": "phase6.1:price-gap",
        }
    )
    source[4] = HistoricalBar.model_validate(gap_content)
    dataset = _dataset_without_coverage(tuple(source))
    orchestrator, _, resolver, receipt = _custom_environment(
        "same-session-gap",
        dataset=dataset,
        execution=execution_configuration(),
    )
    assert receipt.order_id is not None
    projection = _advance_to_terminal(orchestrator, resolver, receipt.order_id)
    terminal = projection.terminal_resolution
    assert terminal is not None
    assert terminal.payload.outcome is ExecutionResolutionOutcome.FILL_READY
    selected = next(
        item
        for item in orchestrator.released_market_events
        if item.market_event_id == terminal.payload.source_market_event_id
    )
    selected_bar = next(bar for bar in dataset.bars if bar.start_at == selected.interval_start_at)
    assert selected_bar.open == Decimal("125")


def test_repeated_resolution_is_byte_identical_and_has_no_duplicate_effect() -> None:
    orchestrator, _, resolver, receipt = _created("repeat-resolution")
    assert receipt.order_id is not None
    first = _advance_to_terminal(orchestrator, resolver, receipt.order_id)
    second = resolver.resolve(receipt.order_id)
    assert first is second
    assert first.revision == second.revision
    assert first.terminal_resolution is not None
    assert second.terminal_resolution is not None
    assert serialize_order_terminal_resolution(first.terminal_resolution) == (
        serialize_order_terminal_resolution(second.terminal_resolution)
    )


def test_identical_reconstruction_inputs_produce_identical_terminal_bytes() -> None:
    first_orchestrator, _, first_resolver, first_receipt = _created("same-input")
    assert first_receipt.order_id is not None
    first = _advance_to_terminal(first_orchestrator, first_resolver, first_receipt.order_id)
    assert first.terminal_resolution is not None

    second = type(first.terminal_resolution).model_validate(
        first.terminal_resolution.model_dump(mode="python")
    )
    assert first.terminal_resolution == second
    assert serialize_order_terminal_resolution(first.terminal_resolution) == (
        serialize_order_terminal_resolution(second)
    )


def test_insufficient_reported_liquidity_rejects_full_fill_without_partial_fill() -> None:
    orchestrator, _, resolver, receipt = _created("liquidity-rejection", participation="0.0000001")
    assert receipt.order_id is not None
    projection = _advance_to_terminal(orchestrator, resolver, receipt.order_id)
    terminal = projection.terminal_resolution
    assert terminal is not None
    assert projection.state is SimulatedOrderProjectionState.REJECTED
    assert terminal.payload.outcome is ExecutionResolutionOutcome.REJECTED
    assert terminal.payload.reason is ExecutionResolutionReason.INSUFFICIENT_LIQUIDITY
    assert terminal.liquidity_outcome is LiquidityResolutionOutcome.INSUFFICIENT_FOR_FULL_FILL
    assert terminal.maximum_fill_quantity is not None
    assert terminal.maximum_fill_quantity < projection.order.quantity


def test_immediate_cancellation_wins_before_eligibility_and_is_idempotent() -> None:
    _, _, resolver, receipt = _created("cancel-before-eligible")
    assert receipt.order_id is not None
    first_command = resolver.request_cancellation(receipt.order_id)
    second_command = resolver.request_cancellation(receipt.order_id)
    assert first_command is second_command
    projection = resolver.resolve(receipt.order_id)
    terminal = projection.terminal_resolution
    assert terminal is not None
    assert projection.state is SimulatedOrderProjectionState.CANCELLED
    assert terminal.payload.outcome is ExecutionResolutionOutcome.CANCELLED
    assert terminal.payload.reason is ExecutionResolutionReason.CANCELLATION_EFFECTIVE


def test_cancellation_after_execution_interval_open_does_not_erase_fill() -> None:
    orchestrator, _, resolver, receipt = _created("late-cancel")
    assert receipt.order_id is not None
    while len(orchestrator.released_market_events) < 6:
        orchestrator.advance()
    resolver.request_cancellation(receipt.order_id)
    projection = resolver.resolve(receipt.order_id)
    terminal = projection.terminal_resolution
    assert terminal is not None
    assert projection.state is SimulatedOrderProjectionState.FILL_READY
    assert terminal.payload.outcome is ExecutionResolutionOutcome.FILL_READY


def test_foreign_order_and_cross_resolver_access_fail_closed() -> None:
    _, _, first, first_receipt = _created("isolated-a")
    _, _, second, second_receipt = _created("isolated-b")
    assert first_receipt.order_id is not None and second_receipt.order_id is not None
    with pytest.raises(OrderProjectionNotFoundError):
        first.projection(second_receipt.order_id)
    with pytest.raises(OrderProjectionNotFoundError):
        second.resolve(first_receipt.order_id)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("agent_id", "agent:forged"),
        ("proposal_id", "sha256:" + "a" * 64),
        ("risk_decision_id", "sha256:" + "b" * 64),
        ("reservation_id", "sha256:" + "c" * 64),
    ],
)
def test_reidentified_foreign_creation_evidence_is_rejected_by_authoritative_context(
    field: str,
    value: str,
) -> None:
    _, result, resolver, command = _environment(f"forged-{field}")
    content = command.model_dump(mode="python", exclude={"command_id"})
    content[field] = value
    forged = OrderCreationCommand.model_validate(
        {"command_id": calculate_order_creation_command_id(content), **content}
    )
    with pytest.raises(OrderResolutionInvariantError, match="authoritative"):
        resolver.create_order(forged, result)


def test_forged_command_identity_fails_model_validation() -> None:
    _, _, _, command = _environment("forged-identity")
    content = command.model_dump(mode="python")
    content["reservation_id"] = "sha256:" + "f" * 64
    with pytest.raises(ValidationError, match="identity"):
        OrderCreationCommand.model_validate(content)


@pytest.mark.parametrize(
    "stage",
    [
        "before_authoritative_result_validation",
        "after_authoritative_result_validation",
        "before_order_creation_commit",
    ],
)
def test_creation_exception_leaves_order_registry_unchanged(stage: str) -> None:
    orchestrator, result, resolver, command = _environment(
        f"create-failure-{stage}", failure_stage=stage
    )
    before = (
        orchestrator.scheduler.position,
        orchestrator.released_market_events,
        orchestrator.scheduler.published_result_ids,
    )
    with pytest.raises(RuntimeError, match=stage):
        resolver.create_order(command, result)
    with pytest.raises(OrderProjectionNotFoundError):
        resolver.projection(SimulatedOrderId.parse("order:never-created"))
    assert (
        orchestrator.scheduler.position,
        orchestrator.released_market_events,
        orchestrator.scheduler.published_result_ids,
    ) == before


def test_terminal_exception_leaves_existing_projection_unchanged() -> None:
    orchestrator, result, resolver, command = _environment(
        "terminal-failure", failure_stage="before_terminal_commit"
    )
    receipt = resolver.create_order(command, result)
    assert receipt.order_id is not None
    before = resolver.projection(receipt.order_id)
    while len(orchestrator.released_market_events) < 6:
        orchestrator.advance()
    orchestration_before = (
        orchestrator.scheduler.position,
        orchestrator.scheduler.published_result_ids,
    )
    with pytest.raises(RuntimeError, match="before_terminal_commit"):
        resolver.resolve(receipt.order_id)
    assert resolver.projection(receipt.order_id) == before
    assert (
        orchestrator.scheduler.position,
        orchestrator.scheduler.published_result_ids,
    ) == orchestration_before


def test_concurrent_repeated_resolution_publishes_one_terminal_projection() -> None:
    orchestrator, _, resolver, receipt = _created("concurrent-resolution")
    assert receipt.order_id is not None
    order_id = receipt.order_id
    while len(orchestrator.released_market_events) < 6:
        orchestrator.advance()
    with ThreadPoolExecutor(max_workers=8) as pool:
        projections = tuple(pool.map(lambda _: resolver.resolve(order_id), range(16)))
    assert len({item.projection_id for item in projections}) == 1
    assert projections[0].terminal_resolution is not None


def test_liquidity_configuration_rejects_float_and_invalid_participation() -> None:
    with pytest.raises(ValidationError, match="Decimal"):
        _liquidity(0.1)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        _liquidity("1.1")
