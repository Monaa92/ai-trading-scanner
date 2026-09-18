from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from simulation_helpers import BASE, digest, initial_portfolio, previous_snapshot_id, run_manifest

from ai_trading_scanner.domain import (
    AgentId,
    InstrumentId,
    PortfolioSnapshotId,
    SimulatedFillId,
    SimulatedOrderId,
    TradeProposalId,
)
from ai_trading_scanner.simulation import (
    CashLedgerSnapshot,
    PortfolioSnapshot,
    PositionChange,
    PositionChangeKind,
    PositionSnapshot,
    RealizedTradeResult,
    calculate_portfolio_snapshot_id,
    calculate_position_change_id,
    calculate_position_id,
    calculate_realized_trade_result_id,
)


def position_snapshot(**changes: object) -> PositionSnapshot:
    manifest = run_manifest(starting_capital="100")
    proposal_id = TradeProposalId.parse(digest("1"))
    instrument_id = InstrumentId.parse("XNYS:AAPL")
    content: dict[str, object] = {
        "schema_version": "position-snapshot-v1",
        "run_id": manifest.run_id,
        "account_id": manifest.account_id,
        "allocation_id": manifest.allocation_id,
        "agent_id": manifest.agent_id,
        "strategy_id": manifest.strategy_id,
        "management_mandate_id": manifest.management_mandate_id,
        "instrument_id": instrument_id,
        "opened_by_proposal_id": proposal_id,
        "currency": "USD",
        "accounting_policy": "WEIGHTED_AVERAGE_LONG_ONLY",
        "opened_at": BASE,
        "marked_at": BASE + timedelta(minutes=1),
        "quantity": "1",
        "average_entry_price": "40",
        "mark_price": "45",
        "gross_cost_basis": "40",
        "market_value": "45",
        "unrealized_gross_pnl": "5",
    }
    content.update(changes)
    agent_id = AgentId.model_validate(content["agent_id"])
    position_id = calculate_position_id(
        manifest.run_id,
        manifest.account_id,
        manifest.allocation_id,
        agent_id,
        instrument_id,
        proposal_id,
    )
    return PositionSnapshot.model_validate({"position_id": position_id, **content})


def marked_portfolio(**changes: object) -> PortfolioSnapshot:
    manifest = run_manifest(starting_capital="100")
    position = position_snapshot()
    content: dict[str, object] = {
        "schema_version": "portfolio-snapshot-v1",
        "run_id": manifest.run_id,
        "account_id": manifest.account_id,
        "allocation_id": manifest.allocation_id,
        "agent_id": manifest.agent_id,
        "previous_snapshot_id": previous_snapshot_id(),
        "as_of": position.marked_at,
        "starting_capital": "100",
        "cash": CashLedgerSnapshot(
            currency="USD",
            available_cash=Decimal("59"),
            reserved_cash=Decimal("0"),
            committed_cash=Decimal("0"),
            total_cash=Decimal("59"),
        ),
        "positions": (position,),
        "realized_gross_pnl": "0",
        "unrealized_gross_pnl": "5",
        "total_execution_costs": "1",
        "gross_trading_pnl": "5",
        "net_trading_pnl": "4",
        "total_equity": "104",
    }
    content.update(changes)
    return PortfolioSnapshot.model_validate(
        {"portfolio_snapshot_id": calculate_portfolio_snapshot_id(content), **content}
    )


def test_initial_portfolio_conserves_cash_and_equity() -> None:
    portfolio = initial_portfolio()

    assert portfolio.cash.total_cash == portfolio.starting_capital
    assert portfolio.total_equity == portfolio.starting_capital
    assert portfolio.gross_trading_pnl == portfolio.net_trading_pnl == Decimal(0)


def test_cash_encumbrances_are_partitions_not_extra_assets() -> None:
    cash = CashLedgerSnapshot(
        currency="USD",
        available_cash=Decimal("35"),
        reserved_cash=Decimal("10"),
        committed_cash=Decimal("5"),
        total_cash=Decimal("50"),
    )
    assert cash.total_cash == Decimal("50")

    with pytest.raises(ValidationError, match="available plus reserved plus committed"):
        CashLedgerSnapshot(
            currency="USD",
            available_cash=Decimal("35"),
            reserved_cash=Decimal("10"),
            committed_cash=Decimal("5"),
            total_cash=Decimal("55"),
        )


def test_position_and_portfolio_reconcile_gross_cost_net_and_equity() -> None:
    position = position_snapshot()
    portfolio = marked_portfolio()

    assert position.unrealized_gross_pnl == Decimal("5")
    assert portfolio.gross_trading_pnl == Decimal("5")
    assert portfolio.net_trading_pnl == Decimal("4")
    assert portfolio.total_equity == Decimal("104")


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("unrealized_gross_pnl", "4", "unrealized"),
        ("gross_trading_pnl", "4", "gross trading"),
        ("net_trading_pnl", "5", "net trading"),
        ("total_equity", "105", "conservation"),
    ],
)
def test_portfolio_conservation_rejects_inconsistent_derived_values(
    field: str, value: str, match: str
) -> None:
    with pytest.raises(ValidationError, match=match):
        marked_portfolio(**{field: value})


def test_portfolio_rejects_cross_agent_position() -> None:
    position = position_snapshot(agent_id="agent:other")
    with pytest.raises(ValidationError, match="attribution"):
        marked_portfolio(positions=(position,))


def test_financial_accounting_rejects_binary_floats() -> None:
    with pytest.raises(ValidationError, match="float"):
        marked_portfolio(total_execution_costs=1.0)
    with pytest.raises(ValidationError, match="float"):
        position_snapshot(mark_price=45.0)


def test_negative_cash_and_costs_fail_closed() -> None:
    with pytest.raises(ValidationError):
        CashLedgerSnapshot(
            currency="USD",
            available_cash=Decimal("-1"),
            reserved_cash=Decimal("0"),
            committed_cash=Decimal("0"),
            total_cash=Decimal("-1"),
        )
    with pytest.raises(ValidationError):
        marked_portfolio(total_execution_costs="-1")


def position_change(**changes: object) -> PositionChange:
    manifest = run_manifest()
    position_id = calculate_position_id(
        manifest.run_id,
        manifest.account_id,
        manifest.allocation_id,
        manifest.agent_id,
        InstrumentId.parse("XNYS:AAPL"),
        TradeProposalId.parse(digest("1")),
    )
    content: dict[str, object] = {
        "schema_version": "position-change-v1",
        "run_id": manifest.run_id,
        "account_id": manifest.account_id,
        "allocation_id": manifest.allocation_id,
        "agent_id": manifest.agent_id,
        "position_id": position_id,
        "proposal_id": TradeProposalId.parse(digest("1")),
        "order_id": SimulatedOrderId.parse(digest("2")),
        "fill_id": SimulatedFillId.parse(digest("3")),
        "management_mandate_id": manifest.management_mandate_id,
        "kind": PositionChangeKind.OPEN,
        "previous_quantity": "0",
        "quantity_delta": "1",
        "new_quantity": "1",
        "changed_at": BASE,
    }
    content.update(changes)
    return PositionChange.model_validate(
        {"position_change_id": calculate_position_change_id(content), **content}
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "OPEN", "previous_quantity": "1", "quantity_delta": "1", "new_quantity": "2"},
        {
            "kind": "INCREASE",
            "previous_quantity": "1",
            "quantity_delta": "-1",
            "new_quantity": "0",
        },
        {
            "kind": "DECREASE",
            "previous_quantity": "1",
            "quantity_delta": "-1",
            "new_quantity": "0",
        },
        {
            "kind": "CLOSE",
            "previous_quantity": "1",
            "quantity_delta": "-0.5",
            "new_quantity": "0.5",
        },
    ],
)
def test_position_lifecycle_transitions_fail_closed(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        position_change(**changes)


def test_position_change_identity_binds_fill_and_management() -> None:
    change = position_change()
    content = change.model_dump(mode="python")
    content["fill_id"] = SimulatedFillId.parse(digest("4"))
    with pytest.raises(ValidationError, match="identity"):
        PositionChange.model_validate(content)


def realized_trade(**changes: object) -> RealizedTradeResult:
    manifest = run_manifest()
    proposal_id = TradeProposalId.parse(digest("1"))
    position_id = calculate_position_id(
        manifest.run_id,
        manifest.account_id,
        manifest.allocation_id,
        manifest.agent_id,
        InstrumentId.parse("XNYS:AAPL"),
        proposal_id,
    )
    content: dict[str, object] = {
        "schema_version": "realized-trade-result-v1",
        "run_id": manifest.run_id,
        "account_id": manifest.account_id,
        "allocation_id": manifest.allocation_id,
        "agent_id": manifest.agent_id,
        "strategy_id": manifest.strategy_id,
        "management_mandate_id": manifest.management_mandate_id,
        "position_id": position_id,
        "proposal_id": proposal_id,
        "entry_fill_ids": (SimulatedFillId.parse(digest("5")),),
        "exit_fill_ids": (SimulatedFillId.parse(digest("6")),),
        "opened_at": BASE,
        "closed_at": BASE + timedelta(minutes=5),
        "quantity": "1",
        "gross_pnl": "5",
        "total_execution_costs": "1",
        "net_pnl": "4",
    }
    content.update(changes)
    return RealizedTradeResult.model_validate(
        {
            "realized_trade_result_id": calculate_realized_trade_result_id(content),
            **content,
        }
    )


def test_realized_trade_reconciles_net_result_and_identity() -> None:
    trade = realized_trade()
    assert trade.net_pnl == trade.gross_pnl - trade.total_execution_costs

    with pytest.raises(ValidationError, match="net P&L"):
        realized_trade(net_pnl="5")


def test_snapshot_identity_changes_with_previous_lineage() -> None:
    first = initial_portfolio()
    second = initial_portfolio(previous_snapshot_id=PortfolioSnapshotId.parse(digest("7")))
    assert first.portfolio_snapshot_id != second.portfolio_snapshot_id


def test_accounting_timestamps_are_causal() -> None:
    with pytest.raises(ValidationError, match="predate"):
        position_snapshot(marked_at=BASE - timedelta(seconds=1))
    assert marked_portfolio().as_of == datetime(2024, 7, 2, 13, 32, 2, tzinfo=UTC)
