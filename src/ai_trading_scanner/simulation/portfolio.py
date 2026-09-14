"""Immutable, Decimal-only portfolio accounting contracts for Phase 6."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import StrEnum
from typing import Annotated, Literal, Self

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
