import ast
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from simulation_helpers import (
    BASE,
    cost_configuration,
    execution_configuration,
    execution_dimensions,
    market_event,
    run_manifest,
    simulated_fill,
    simulated_order,
)

from ai_trading_scanner.domain.execution import DataRunMode, ExecutionEnvironment
from ai_trading_scanner.simulation import (
    SimulatedOrder,
    calculate_fill_costs,
    calculate_simulated_order_id,
    validate_fill_against_order,
)


def test_run_manifest_is_content_identified_and_immutable() -> None:
    first = run_manifest()
    second = run_manifest()

    assert first == second
    assert str(first.run_id).startswith("sha256:")
    with pytest.raises(ValidationError, match="frozen"):
        first.starting_capital = Decimal("100")


def test_run_identity_changes_with_any_economic_model() -> None:
    original = run_manifest()
    changed_costs = cost_configuration(profile_version="v2")
    changed_execution = execution_configuration(routing_latency_seconds=2)

    assert run_manifest(cost_model_id=changed_costs.cost_model_id).run_id != original.run_id
    assert (
        run_manifest(execution_model_id=changed_execution.execution_model_id).run_id
        != original.run_id
    )
    assert run_manifest(starting_capital="100").run_id != original.run_id


@pytest.mark.parametrize(
    "changes",
    [
        {"execution_dimensions": execution_dimensions(execution_environment="PAPER")},
        {"execution_dimensions": execution_dimensions(execution_environment="LIVE")},
        {"execution_dimensions": execution_dimensions(data_run_mode=DataRunMode.LIVE_FEED)},
    ],
)
def test_phase6_manifest_rejects_non_replay_or_non_simulation_authority(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="SIMULATION|historical or captured"):
        run_manifest(**changes)


def test_full_auto_remains_independent_from_simulation_environment() -> None:
    manifest = run_manifest()

    assert manifest.execution_dimensions.approval_policy.value == "FULL_AUTO"
    assert manifest.execution_dimensions.execution_environment is ExecutionEnvironment.SIMULATION


@pytest.mark.parametrize(
    ("factory", "changes", "match"),
    [
        (market_event, {"available_at": BASE - timedelta(seconds=1)}, "available"),
        (simulated_order, {"submitted_at": BASE - timedelta(seconds=1)}, "submission"),
        (simulated_order, {"eligible_at": BASE}, "eligibility"),
        (
            simulated_fill,
            {"execution_interval_start_at": BASE + timedelta(seconds=1)},
            "interval|market-event",
        ),
        (
            simulated_fill,
            {"eligible_at": datetime(2024, 7, 2, 13, 32, tzinfo=UTC)},
            "strictly later",
        ),
        (simulated_fill, {"fill_at": BASE}, "price source"),
    ],
)
def test_invalid_causal_timestamp_ordering_fails_closed(
    factory: object, changes: dict[str, object], match: str
) -> None:
    with pytest.raises(ValidationError, match=match):
        factory(**changes)  # type: ignore[operator]


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (execution_configuration, "quantity_increment"),
        (cost_configuration, "commission_per_share"),
        (run_manifest, "starting_capital"),
        (simulated_order, "quantity"),
        (simulated_fill, "fill_price"),
    ],
)
def test_financial_contracts_reject_binary_float(factory: object, field: str) -> None:
    with pytest.raises(ValidationError, match="float"):
        factory(**{field: 1.0})  # type: ignore[operator]


@pytest.mark.parametrize(
    ("factory", "field", "value"),
    [
        (execution_configuration, "quantity_increment", "0"),
        (cost_configuration, "spread_bps", "-1"),
        (run_manifest, "starting_capital", "-50"),
        (simulated_order, "quantity", "-1"),
        (simulated_fill, "fill_price", "0"),
    ],
)
def test_invalid_negative_or_zero_financial_values_fail_closed(
    factory: object, field: str, value: str
) -> None:
    with pytest.raises(ValidationError):
        factory(**{field: value})  # type: ignore[operator]


def test_execution_configuration_rejects_unsupported_v1_assumptions() -> None:
    with pytest.raises(ValidationError):
        execution_configuration(partial_fills_supported=True)
    with pytest.raises(ValidationError):
        execution_configuration(fill_price_policy="SAME_BAR_CLOSE")
    with pytest.raises(ValidationError):
        execution_configuration(randomness_policy="UNSEEDED")


def test_cost_breakdown_uses_every_configured_component() -> None:
    costs = calculate_fill_costs(cost_configuration(), Decimal("2"), Decimal("100"))

    assert costs.commission == Decimal("0.35")
    assert costs.spread == Decimal("0.04")
    assert costs.slippage == Decimal("0.06")
    assert costs.other_fees == Decimal("0.002")
    assert costs.total == Decimal("0.452")


def test_fill_cost_calculation_rejects_float_inputs() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        calculate_fill_costs(cost_configuration(), 1.0, Decimal("100"))  # type: ignore[arg-type]


def test_fill_is_causally_and_immutably_bound_to_order() -> None:
    order = simulated_order()
    fill = simulated_fill()

    validate_fill_against_order(fill, order)
    assert fill.simulated_execution_at > order.submitted_at
    assert fill.fill_at >= fill.market_event.available_at


def test_partial_or_cross_agent_fill_is_rejected() -> None:
    order = simulated_order()
    partial_costs = calculate_fill_costs(cost_configuration(), Decimal("0.5"), Decimal("100"))
    partial = simulated_fill(quantity="0.5", costs=partial_costs)
    with pytest.raises(ValueError, match="partial"):
        validate_fill_against_order(partial, order)

    foreign_content = order.model_dump(mode="python", exclude={"order_id"})
    foreign_content["agent_id"] = "agent:other"
    foreign = SimulatedOrder.model_validate(
        {"order_id": calculate_simulated_order_id(foreign_content), **foreign_content}
    )
    with pytest.raises(ValueError, match="attribution"):
        validate_fill_against_order(simulated_fill(), foreign)


def test_order_identity_detects_immutable_linkage_change() -> None:
    order = simulated_order()
    content = order.model_dump(mode="python")
    content["valid_until"] = order.valid_until + timedelta(minutes=1)

    with pytest.raises(ValidationError, match="identity"):
        SimulatedOrder.model_validate(content)


def test_timestamps_normalize_to_utc() -> None:
    eastern = timezone(timedelta(hours=-4))
    order = simulated_order(decision_at=datetime(2024, 7, 2, 9, 31, 2, tzinfo=eastern))

    assert order.decision_at == BASE
    assert order.decision_at.tzinfo is UTC


def test_simulation_foundation_has_no_broker_provider_network_or_ai_imports() -> None:
    package = Path("src/ai_trading_scanner/simulation")
    forbidden = {
        "alpaca",
        "anthropic",
        "httpx",
        "ib_insync",
        "kraken",
        "openai",
        "requests",
        "socket",
        "urllib",
        "yfinance",
    }
    imported: set[str] = set()
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])

    assert forbidden.isdisjoint(imported)
