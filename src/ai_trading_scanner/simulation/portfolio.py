"""Immutable, Decimal-only portfolio accounting contracts for Phase 6."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import StrEnum
from itertools import pairwise
from typing import TYPE_CHECKING, Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_trading_scanner.domain import (
    AccountId,
    AgentId,
    AllocationId,
    InstrumentId,
    ManagementMandateId,
    PortfolioSnapshotId,
    PositionChangeId,
    PositionId,
    RealizedTradeResultId,
    SimulatedFillId,
    SimulatedOrderId,
    SimulationRunId,
    StrategyId,
    TradeProposalId,
)
from ai_trading_scanner.domain.content_identity import sha256_content_id_v2

if TYPE_CHECKING:
    from ai_trading_scanner.simulation.models import (
        SimulatedFill,
        SimulationRunManifest,
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _reject_float(value: object, label: str) -> object:
    if isinstance(value, float):
        raise ValueError(f"{label} must use Decimal or decimal strings, not float")
    return value


def _identity_content(value: BaseModel | dict[str, object], field: str) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude={field})
    return {key: item for key, item in value.items() if key != field}


def _normalized_decimal_content(
    value: BaseModel | dict[str, object], identity_field: str, fields: tuple[str, ...]
) -> dict[str, object]:
    content = _identity_content(value, identity_field)
    for field in fields:
        item = content.get(field)
        if item is not None and not isinstance(item, Decimal | float):
            content[field] = Decimal(item)  # type: ignore[arg-type]
    return content


class PositionAccountingPolicy(StrEnum):
    WEIGHTED_AVERAGE_LONG_ONLY = "WEIGHTED_AVERAGE_LONG_ONLY"


class PositionChangeKind(StrEnum):
    OPEN = "OPEN"
    DECREASE = "DECREASE"
    CLOSE = "CLOSE"


class CashLedgerSnapshot(BaseModel):
    """Cash encumbrances are partitions of cash, never additional assets."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    available_cash: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    reserved_cash: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    committed_cash: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    total_cash: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]

    @field_validator(
        "available_cash", "reserved_cash", "committed_cash", "total_cash", mode="before"
    )
    @classmethod
    def reject_float_values(cls, value: object) -> object:
        return _reject_float(value, "cash value")

    @model_validator(mode="after")
    def validate_conservation(self) -> Self:
        with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
            expected = self.available_cash + self.reserved_cash + self.committed_cash
        if self.total_cash != expected:
            raise ValueError("total cash must equal available plus reserved plus committed cash")
        return self


class PositionSnapshot(BaseModel):
    """One open long-only position under weighted-average V1 accounting."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    position_id: PositionId
    schema_version: Literal["position-snapshot-v1"] = "position-snapshot-v1"
    run_id: SimulationRunId
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    strategy_id: StrategyId
    management_mandate_id: ManagementMandateId
    instrument_id: InstrumentId
    opened_by_proposal_id: TradeProposalId
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    accounting_policy: Literal[PositionAccountingPolicy.WEIGHTED_AVERAGE_LONG_ONLY] = (
        PositionAccountingPolicy.WEIGHTED_AVERAGE_LONG_ONLY
    )
    opened_at: datetime
    marked_at: datetime
    quantity: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    average_entry_price: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    mark_price: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    gross_cost_basis: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    market_value: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    unrealized_gross_pnl: Annotated[Decimal, Field(allow_inf_nan=False)]

    @field_validator("opened_at", "marked_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @field_validator(
        "quantity",
        "average_entry_price",
        "mark_price",
        "gross_cost_basis",
        "market_value",
        "unrealized_gross_pnl",
        mode="before",
    )
    @classmethod
    def reject_float_values(cls, value: object) -> object:
        return _reject_float(value, "position financial value")

    @model_validator(mode="after")
    def validate_position(self) -> Self:
        if self.marked_at < self.opened_at:
            raise ValueError("position mark cannot predate opening")
        with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
            expected_cost_basis = self.quantity * self.average_entry_price
            expected_market_value = self.quantity * self.mark_price
            expected_unrealized = expected_market_value - expected_cost_basis
        if self.gross_cost_basis != expected_cost_basis:
            raise ValueError("gross cost basis must equal quantity times average entry price")
        if self.market_value != expected_market_value:
            raise ValueError("market value must equal quantity times mark price")
        if self.unrealized_gross_pnl != expected_unrealized:
            raise ValueError("unrealized gross P&L must equal market value minus gross cost basis")
        if self.position_id != calculate_position_id(
            self.run_id,
            self.account_id,
            self.allocation_id,
            self.agent_id,
            self.instrument_id,
            self.opened_by_proposal_id,
        ):
            raise ValueError("position identity does not match opening lineage")
        return self


def calculate_position_id(
    run_id: SimulationRunId,
    account_id: AccountId,
    allocation_id: AllocationId,
    agent_id: AgentId,
    instrument_id: InstrumentId,
    opened_by_proposal_id: TradeProposalId,
) -> PositionId:
    return PositionId.parse(
        sha256_content_id_v2(
            {
                "run_id": run_id,
                "account_id": account_id,
                "allocation_id": allocation_id,
                "agent_id": agent_id,
                "instrument_id": instrument_id,
                "opened_by_proposal_id": opened_by_proposal_id,
            }
        )
    )


class PortfolioSnapshot(BaseModel):
    """Conserved one-currency participant portfolio projection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    portfolio_snapshot_id: PortfolioSnapshotId
    schema_version: Literal["portfolio-snapshot-v1"] = "portfolio-snapshot-v1"
    run_id: SimulationRunId
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    previous_snapshot_id: PortfolioSnapshotId | None = None
    as_of: datetime
    starting_capital: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    cash: CashLedgerSnapshot
    positions: tuple[PositionSnapshot, ...] = ()
    realized_gross_pnl: Annotated[Decimal, Field(allow_inf_nan=False)]
    unrealized_gross_pnl: Annotated[Decimal, Field(allow_inf_nan=False)]
    total_execution_costs: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    gross_trading_pnl: Annotated[Decimal, Field(allow_inf_nan=False)]
    net_trading_pnl: Annotated[Decimal, Field(allow_inf_nan=False)]
    total_equity: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]

    @field_validator("as_of")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @field_validator(
        "starting_capital",
        "realized_gross_pnl",
        "unrealized_gross_pnl",
        "total_execution_costs",
        "gross_trading_pnl",
        "net_trading_pnl",
        "total_equity",
        mode="before",
    )
    @classmethod
    def reject_float_values(cls, value: object) -> object:
        return _reject_float(value, "portfolio financial value")

    @model_validator(mode="after")
    def validate_portfolio(self) -> Self:
        position_ids = tuple(position.position_id for position in self.positions)
        instruments = tuple(position.instrument_id for position in self.positions)
        if len(set(position_ids)) != len(position_ids) or len(set(instruments)) != len(instruments):
            raise ValueError("portfolio positions must have unique identities and instruments")
        if position_ids != tuple(sorted(position_ids, key=str)):
            raise ValueError("portfolio positions must use canonical position-id order")
        if any(
            position.run_id != self.run_id
            or position.account_id != self.account_id
            or position.allocation_id != self.allocation_id
            or position.agent_id != self.agent_id
            or position.marked_at > self.as_of
            for position in self.positions
        ):
            raise ValueError("portfolio position attribution or causal mark differs")
        with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
            market_value = sum((position.market_value for position in self.positions), Decimal(0))
            unrealized = sum(
                (position.unrealized_gross_pnl for position in self.positions), Decimal(0)
            )
            gross = self.realized_gross_pnl + unrealized
            net = gross - self.total_execution_costs
            equity = self.cash.total_cash + market_value
            conserved_equity = self.starting_capital + net
        if any(position.currency != self.cash.currency for position in self.positions):
            raise ValueError("portfolio cash and position currencies differ")
        if self.unrealized_gross_pnl != unrealized:
            raise ValueError("portfolio unrealized P&L does not equal open positions")
        if self.gross_trading_pnl != gross:
            raise ValueError("gross trading P&L must equal realized plus unrealized gross P&L")
        if self.net_trading_pnl != net:
            raise ValueError("net trading P&L must equal gross P&L minus execution costs")
        if self.total_equity != equity or self.total_equity != conserved_equity:
            raise ValueError("portfolio equity conservation failed")
        if self.portfolio_snapshot_id != calculate_portfolio_snapshot_id(self):
            raise ValueError("portfolio snapshot identity does not match content")
        return self


def calculate_portfolio_snapshot_id(
    snapshot: PortfolioSnapshot | dict[str, object],
) -> PortfolioSnapshotId:
    content = _normalized_decimal_content(
        snapshot,
        "portfolio_snapshot_id",
        (
            "starting_capital",
            "realized_gross_pnl",
            "unrealized_gross_pnl",
            "total_execution_costs",
            "gross_trading_pnl",
            "net_trading_pnl",
            "total_equity",
        ),
    )
    return PortfolioSnapshotId.parse(sha256_content_id_v2(content))


class PositionChange(BaseModel):
    """Immutable fill-linked quantity transition for one position episode."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    position_change_id: PositionChangeId
    schema_version: Literal["position-change-v1"] = "position-change-v1"
    run_id: SimulationRunId
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    position_id: PositionId
    proposal_id: TradeProposalId
    order_id: SimulatedOrderId
    fill_id: SimulatedFillId
    management_mandate_id: ManagementMandateId
    kind: PositionChangeKind
    previous_quantity: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    quantity_delta: Annotated[Decimal, Field(allow_inf_nan=False)]
    new_quantity: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    changed_at: datetime

    @field_validator("previous_quantity", "quantity_delta", "new_quantity", mode="before")
    @classmethod
    def reject_float_values(cls, value: object) -> object:
        return _reject_float(value, "position quantity")

    @field_validator("changed_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_change(self) -> Self:
        if (
            self.quantity_delta == 0
            or self.new_quantity != self.previous_quantity + self.quantity_delta
        ):
            raise ValueError("position quantities must describe one nonzero conserved change")
        if self.kind is PositionChangeKind.OPEN and not (
            self.previous_quantity == 0 and self.quantity_delta > 0 and self.new_quantity > 0
        ):
            raise ValueError("OPEN must transition zero quantity to a positive position")
        if self.kind is PositionChangeKind.DECREASE and not (
            self.previous_quantity > 0 and self.quantity_delta < 0 and self.new_quantity > 0
        ):
            raise ValueError("DECREASE must leave a positive residual position")
        if self.kind is PositionChangeKind.CLOSE and not (
            self.previous_quantity > 0 and self.quantity_delta < 0 and self.new_quantity == 0
        ):
            raise ValueError("CLOSE must reduce an open position exactly to zero")
        if self.position_change_id != calculate_position_change_id(self):
            raise ValueError("position change identity does not match content")
        return self


def calculate_position_change_id(
    change: PositionChange | dict[str, object],
) -> PositionChangeId:
    content = _normalized_decimal_content(
        change,
        "position_change_id",
        ("previous_quantity", "quantity_delta", "new_quantity"),
    )
    return PositionChangeId.parse(sha256_content_id_v2(content))


class RealizedTradeResult(BaseModel):
    """Closed position-episode result with explicit gross/cost/net reconciliation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    realized_trade_result_id: RealizedTradeResultId
    schema_version: Literal["realized-trade-result-v1"] = "realized-trade-result-v1"
    run_id: SimulationRunId
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    strategy_id: StrategyId
    management_mandate_id: ManagementMandateId
    position_id: PositionId
    proposal_id: TradeProposalId
    entry_fill_ids: tuple[SimulatedFillId, ...] = Field(min_length=1)
    exit_fill_ids: tuple[SimulatedFillId, ...] = Field(min_length=1)
    opened_at: datetime
    closed_at: datetime
    quantity: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    gross_pnl: Annotated[Decimal, Field(allow_inf_nan=False)]
    total_execution_costs: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    net_pnl: Annotated[Decimal, Field(allow_inf_nan=False)]

    @field_validator("opened_at", "closed_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @field_validator("quantity", "gross_pnl", "total_execution_costs", "net_pnl", mode="before")
    @classmethod
    def reject_float_values(cls, value: object) -> object:
        return _reject_float(value, "realized-trade financial value")

    @model_validator(mode="after")
    def validate_trade(self) -> Self:
        if self.closed_at < self.opened_at:
            raise ValueError("realized trade cannot close before it opens")
        if len(set(self.entry_fill_ids)) != len(self.entry_fill_ids) or len(
            set(self.exit_fill_ids)
        ) != len(self.exit_fill_ids):
            raise ValueError("realized trade fill identities must be unique")
        if set(self.entry_fill_ids).intersection(self.exit_fill_ids):
            raise ValueError("one fill cannot be both entry and exit")
        if self.net_pnl != self.gross_pnl - self.total_execution_costs:
            raise ValueError("realized net P&L must equal gross P&L minus execution costs")
        if self.realized_trade_result_id != calculate_realized_trade_result_id(self):
            raise ValueError("realized trade result identity does not match content")
        return self


def calculate_realized_trade_result_id(
    result: RealizedTradeResult | dict[str, object],
) -> RealizedTradeResultId:
    content = _normalized_decimal_content(
        result,
        "realized_trade_result_id",
        ("quantity", "gross_pnl", "total_execution_costs", "net_pnl"),
    )
    return RealizedTradeResultId.parse(sha256_content_id_v2(content))


@dataclass
class _OpenPositionState:
    position_id: PositionId
    proposal_id: TradeProposalId
    management_mandate_id: ManagementMandateId
    instrument_id: InstrumentId
    currency: str
    opened_at: datetime
    quantity: Decimal
    average_entry_price: Decimal
    original_quantity: Decimal
    entry_fill_ids: list[SimulatedFillId] = dataclass_field(default_factory=list)
    exit_fill_ids: list[SimulatedFillId] = dataclass_field(default_factory=list)
    execution_costs: Decimal = Decimal(0)
    realized_gross_pnl: Decimal = Decimal(0)
    last_fill_price: Decimal = Decimal(0)
    last_fill_at: datetime | None = None


def reconcile_complete_portfolio(
    manifest: SimulationRunManifest,
    fills: tuple[SimulatedFill, ...],
    changes: tuple[PositionChange, ...],
    snapshots: tuple[PortfolioSnapshot, ...],
    realized_trades: tuple[RealizedTradeResult, ...],
) -> None:
    """Derive and verify every COMPLETE V1 accounting projection.

    This is a pure in-memory verifier, not a durable posting service. The V1
    valuation policy marks an open position at its latest applied fill price;
    a later market valuation contract is intentionally outside this foundation.
    """
    from ai_trading_scanner.simulation.models import SimulatedOrderSide

    ordered_snapshots = tuple(
        sorted(snapshots, key=lambda item: (item.as_of, str(item.portfolio_snapshot_id)))
    )
    initial = tuple(item for item in ordered_snapshots if item.previous_snapshot_id is None)
    if len(initial) != 1 or ordered_snapshots[0] != initial[0]:
        raise ValueError("complete accounting requires one earliest starting portfolio")
    starting = initial[0]
    if (
        starting.positions
        or starting.cash.currency != manifest.reporting_currency
        or starting.cash.available_cash != manifest.starting_capital
        or starting.cash.reserved_cash != 0
        or starting.cash.committed_cash != 0
        or starting.cash.total_cash != manifest.starting_capital
        or starting.realized_gross_pnl != 0
        or starting.unrealized_gross_pnl != 0
        or starting.total_execution_costs != 0
        or starting.gross_trading_pnl != 0
        or starting.net_trading_pnl != 0
        or starting.total_equity != manifest.starting_capital
    ):
        raise ValueError("starting portfolio is not the flat unencumbered run capital")
    if fills and starting.as_of > min(fill.submitted_at for fill in fills):
        raise ValueError("starting portfolio postdates the first submitted order")
    if any(fill.currency != manifest.reporting_currency for fill in fills):
        raise ValueError("fill currency differs from the single-currency run ledger")
    for previous, current in pairwise(ordered_snapshots):
        if current.previous_snapshot_id != previous.portfolio_snapshot_id:
            raise ValueError("portfolio snapshot lineage is not chronological and contiguous")

    fill_by_id = {fill.fill_id: fill for fill in fills}
    if len(fill_by_id) != len(fills):
        raise ValueError("complete accounting contains duplicate fills")
    changed_fill_ids = tuple(change.fill_id for change in changes)
    if len(set(changed_fill_ids)) != len(changed_fill_ids):
        raise ValueError("one fill cannot be applied through multiple position changes")
    if set(changed_fill_ids) != set(fill_by_id):
        raise ValueError("complete accounting requires exactly one application per fill")

    ordered_changes = tuple(
        sorted(changes, key=lambda item: (item.changed_at, str(item.position_change_id)))
    )
    open_positions: dict[InstrumentId, _OpenPositionState] = {}
    cash = manifest.starting_capital
    realized_gross = Decimal(0)
    total_costs = Decimal(0)
    derived_trades: list[RealizedTradeResult] = []
    change_index = 0

    def apply(change: PositionChange) -> None:
        nonlocal cash, realized_gross, total_costs
        fill = fill_by_id[change.fill_id]
        if (
            change.run_id != fill.run_id
            or change.account_id != fill.account_id
            or change.allocation_id != fill.allocation_id
            or change.agent_id != fill.agent_id
            or change.proposal_id != fill.proposal_id
            or change.order_id != fill.order_id
            or change.changed_at != fill.fill_at
        ):
            raise ValueError("position change references a foreign or unrelated fill")
        expected_position_id = calculate_position_id(
            fill.run_id,
            fill.account_id,
            fill.allocation_id,
            fill.agent_id,
            fill.instrument_id,
            fill.proposal_id,
        )
        if change.position_id != expected_position_id:
            raise ValueError("position change identity does not match its fill lineage")
        with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
            notional = fill.quantity * fill.fill_price
            total_costs += fill.costs.total
            if fill.side is SimulatedOrderSide.BUY:
                if fill.instrument_id in open_positions:
                    raise ValueError("V1 accounting does not permit scale-in applications")
                if (
                    change.kind is not PositionChangeKind.OPEN
                    or change.previous_quantity != 0
                    or change.quantity_delta != fill.quantity
                    or change.new_quantity != fill.quantity
                ):
                    raise ValueError("buy fill is not applied as one exact OPEN transition")
                cash -= notional + fill.costs.total
                if cash < 0:
                    raise ValueError("fill application would make portfolio cash negative")
                open_positions[fill.instrument_id] = _OpenPositionState(
                    position_id=change.position_id,
                    proposal_id=change.proposal_id,
                    management_mandate_id=change.management_mandate_id,
                    instrument_id=fill.instrument_id,
                    currency=fill.currency,
                    opened_at=fill.fill_at,
                    quantity=fill.quantity,
                    average_entry_price=fill.fill_price,
                    original_quantity=fill.quantity,
                    entry_fill_ids=[fill.fill_id],
                    execution_costs=fill.costs.total,
                    last_fill_price=fill.fill_price,
                    last_fill_at=fill.fill_at,
                )
                return

            position = open_positions.get(fill.instrument_id)
            if position is None or position.position_id != change.position_id:
                raise ValueError("sell fill references no matching open position")
            if (
                change.previous_quantity != position.quantity
                or change.quantity_delta != -fill.quantity
                or change.new_quantity != position.quantity - fill.quantity
                or change.management_mandate_id != position.management_mandate_id
            ):
                raise ValueError("sell fill quantity or mandate is not causally conserved")
            expected_kind = (
                PositionChangeKind.CLOSE
                if change.new_quantity == 0
                else PositionChangeKind.DECREASE
            )
            if change.kind is not expected_kind:
                raise ValueError("sell fill position-change kind does not match residual quantity")
            gross = fill.quantity * (fill.fill_price - position.average_entry_price)
            cash += notional - fill.costs.total
            realized_gross += gross
            position.realized_gross_pnl += gross
            position.execution_costs += fill.costs.total
            position.quantity = change.new_quantity
            position.exit_fill_ids.append(fill.fill_id)
            position.last_fill_price = fill.fill_price
            position.last_fill_at = fill.fill_at
            if change.new_quantity == 0:
                trade_content: dict[str, object] = {
                    "schema_version": "realized-trade-result-v1",
                    "run_id": manifest.run_id,
                    "account_id": manifest.account_id,
                    "allocation_id": manifest.allocation_id,
                    "agent_id": manifest.agent_id,
                    "strategy_id": manifest.strategy_id,
                    "management_mandate_id": position.management_mandate_id,
                    "position_id": position.position_id,
                    "proposal_id": position.proposal_id,
                    "entry_fill_ids": tuple(position.entry_fill_ids),
                    "exit_fill_ids": tuple(position.exit_fill_ids),
                    "opened_at": position.opened_at,
                    "closed_at": fill.fill_at,
                    "quantity": position.original_quantity,
                    "gross_pnl": position.realized_gross_pnl,
                    "total_execution_costs": position.execution_costs,
                    "net_pnl": position.realized_gross_pnl - position.execution_costs,
                }
                derived_trades.append(
                    RealizedTradeResult.model_validate(
                        {
                            "realized_trade_result_id": calculate_realized_trade_result_id(
                                trade_content
                            ),
                            **trade_content,
                        }
                    )
                )
                del open_positions[fill.instrument_id]

    for snapshot_index, snapshot in enumerate(ordered_snapshots):
        if snapshot_index == 0:
            continue
        while change_index < len(ordered_changes) and (
            ordered_changes[change_index].changed_at <= snapshot.as_of
        ):
            apply(ordered_changes[change_index])
            change_index += 1
        positions: list[PositionSnapshot] = []
        for state in open_positions.values():
            assert state.last_fill_at is not None
            with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
                cost_basis = state.quantity * state.average_entry_price
                market_value = state.quantity * state.last_fill_price
                unrealized = market_value - cost_basis
            positions.append(
                PositionSnapshot(
                    position_id=state.position_id,
                    run_id=manifest.run_id,
                    account_id=manifest.account_id,
                    allocation_id=manifest.allocation_id,
                    agent_id=manifest.agent_id,
                    strategy_id=manifest.strategy_id,
                    management_mandate_id=state.management_mandate_id,
                    instrument_id=state.instrument_id,
                    opened_by_proposal_id=state.proposal_id,
                    currency=state.currency,
                    opened_at=state.opened_at,
                    marked_at=state.last_fill_at,
                    quantity=state.quantity,
                    average_entry_price=state.average_entry_price,
                    mark_price=state.last_fill_price,
                    gross_cost_basis=cost_basis,
                    market_value=market_value,
                    unrealized_gross_pnl=unrealized,
                )
            )
        canonical_positions = tuple(sorted(positions, key=lambda item: str(item.position_id)))
        with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
            unrealized_total = sum(
                (position.unrealized_gross_pnl for position in canonical_positions), Decimal(0)
            )
            gross = realized_gross + unrealized_total
            net = gross - total_costs
            equity = manifest.starting_capital + net
        expected_content: dict[str, object] = {
            "schema_version": "portfolio-snapshot-v1",
            "run_id": manifest.run_id,
            "account_id": manifest.account_id,
            "allocation_id": manifest.allocation_id,
            "agent_id": manifest.agent_id,
            "previous_snapshot_id": snapshot.previous_snapshot_id,
            "as_of": snapshot.as_of,
            "starting_capital": manifest.starting_capital,
            "cash": CashLedgerSnapshot(
                currency=manifest.reporting_currency,
                available_cash=cash,
                reserved_cash=Decimal(0),
                committed_cash=Decimal(0),
                total_cash=cash,
            ),
            "positions": canonical_positions,
            "realized_gross_pnl": realized_gross,
            "unrealized_gross_pnl": unrealized_total,
            "total_execution_costs": total_costs,
            "gross_trading_pnl": gross,
            "net_trading_pnl": net,
            "total_equity": equity,
        }
        expected = PortfolioSnapshot.model_validate(
            {
                "portfolio_snapshot_id": calculate_portfolio_snapshot_id(expected_content),
                **expected_content,
            }
        )
        if snapshot != expected:
            raise ValueError("portfolio snapshot differs from derived chronological accounting")

    if change_index != len(ordered_changes):
        raise ValueError("final portfolio omits one or more accounting transitions")
    if tuple(sorted(derived_trades, key=lambda item: str(item.realized_trade_result_id))) != tuple(
        sorted(realized_trades, key=lambda item: str(item.realized_trade_result_id))
    ):
        raise ValueError("realized trades differ from the derived position lifecycle")
