"""Immutable contracts for deterministic, offline causal simulation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import IntEnum, StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_trading_scanner.domain import (
    AccountId,
    AgentId,
    AllocationId,
    ConfigurationVersionId,
    DatasetId,
    IndicatorConfigurationId,
    InstrumentId,
    ManagementMandateId,
    MarketEventId,
    ModelId,
    ReplayEventId,
    ReservationId,
    RiskConfigurationId,
    RiskDecisionId,
    SimulatedFillId,
    SimulatedOrderId,
    SimulationExecutionModelId,
    SimulationLiquidityModelId,
    SimulationRunId,
    StrategyConfigurationId,
    StrategyDecisionId,
    StrategyId,
    TradeProposalId,
    TransactionCostModelId,
)
from ai_trading_scanner.domain.content_identity import canonical_json_bytes_v2, sha256_content_id_v2
from ai_trading_scanner.domain.execution import (
    DataRunMode,
    ExecutionDimensions,
    ExecutionEnvironment,
)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _identity_content(
    value: BaseModel | dict[str, object], identity_field: str
) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude={identity_field})
    return {key: item for key, item in value.items() if key != identity_field}


def _reject_float(value: object, label: str) -> object:
    if isinstance(value, float):
        raise ValueError(f"{label} must use Decimal or decimal strings, not float")
    return value


def _normalized_decimal_content(
    value: BaseModel | dict[str, object], identity_field: str, fields: tuple[str, ...]
) -> dict[str, object]:
    content = _identity_content(value, identity_field)
    for field in fields:
        item = content.get(field)
        if item is not None and not isinstance(item, Decimal | float):
            content[field] = Decimal(item)  # type: ignore[arg-type]
    return content


class ReplayPhase(IntEnum):
    """Versioned same-timestamp ordering for the Phase 6 V1 event trace."""

    EXECUTION_RESOLUTION = 10
    FILL = 20
    PORTFOLIO_UPDATE = 30
    SESSION_CONTROL = 40
    MARKET_DATA_AVAILABLE = 50
    INDICATOR_UPDATE = 60
    STRATEGY_EVALUATION = 70
    RISK_EVALUATION = 80
    ORDER_SUBMISSION = 90
    RESULT_FINALIZATION = 100


class ReplayPayloadKind(StrEnum):
    EXECUTION_RESOLUTION = "EXECUTION_RESOLUTION"
    SESSION_CONTROL = "SESSION_CONTROL"
    MARKET_EVENT = "MARKET_EVENT"
    INDICATOR_UPDATE = "INDICATOR_UPDATE"
    STRATEGY_DECISION = "STRATEGY_DECISION"
    RISK_DECISION = "RISK_DECISION"
    SIMULATED_ORDER = "SIMULATED_ORDER"
    SIMULATED_FILL = "SIMULATED_FILL"
    POSITION_CHANGE = "POSITION_CHANGE"
    PORTFOLIO_SNAPSHOT = "PORTFOLIO_SNAPSHOT"
    REALIZED_TRADE = "REALIZED_TRADE"
    RUN_RESULT = "RUN_RESULT"


class FillPricePolicy(StrEnum):
    NEXT_ELIGIBLE_BAR_OPEN = "NEXT_ELIGIBLE_BAR_OPEN"


class MissingExecutionDataPolicy(StrEnum):
    EXPIRE_UNFILLED = "EXPIRE_UNFILLED"


class GapPolicy(StrEnum):
    USE_NEXT_ELIGIBLE_OPEN = "USE_NEXT_ELIGIBLE_OPEN"


class IntrabarAmbiguityPolicy(StrEnum):
    STOP_FIRST = "STOP_FIRST"


class RandomnessPolicy(StrEnum):
    NONE = "NONE"


class ReplayTieBreakPolicy(StrEnum):
    SEMANTIC_PAYLOAD_V1 = "SEMANTIC_PAYLOAD_V1"


_SEMANTIC_PAYLOAD_KIND_RANK_V1: dict[ReplayPayloadKind, int] = {
    ReplayPayloadKind.POSITION_CHANGE: 10,
    ReplayPayloadKind.REALIZED_TRADE: 20,
    ReplayPayloadKind.PORTFOLIO_SNAPSHOT: 30,
}


class SimulatedOrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class SimulatedOrderType(StrEnum):
    MARKET = "MARKET"


class SimulationResultStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    ABORTED = "ABORTED"


class MarketEventReference(BaseModel):
    """Stable causal reference to a canonical market observation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    market_event_id: MarketEventId
    schema_version: Literal["market-event-reference-v1"] = "market-event-reference-v1"
    dataset_id: DatasetId
    instrument_id: InstrumentId
    interval_start_at: datetime
    event_at: datetime
    available_at: datetime
    source_record_id: str | None = None

    @field_validator("interval_start_at", "event_at", "available_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        if self.event_at <= self.interval_start_at:
            raise ValueError("market event interval end must follow its start")
        if self.available_at < self.event_at:
            raise ValueError("market event cannot be available before event_at")
        if self.market_event_id != calculate_market_event_id(self):
            raise ValueError("market event identity does not match content")
        return self


def calculate_market_event_id(
    event: MarketEventReference | dict[str, object],
) -> MarketEventId:
    return MarketEventId.parse(sha256_content_id_v2(_identity_content(event, "market_event_id")))


class SimulationExecutionConfiguration(BaseModel):
    """Fail-closed V1 bar execution assumptions; this grants no broker authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_model_id: SimulationExecutionModelId
    schema_version: Literal["simulation-execution-v1"] = "simulation-execution-v1"
    model_version: str = Field(min_length=1)
    fill_price_policy: Literal[FillPricePolicy.NEXT_ELIGIBLE_BAR_OPEN] = (
        FillPricePolicy.NEXT_ELIGIBLE_BAR_OPEN
    )
    routing_latency_seconds: Annotated[int, Field(ge=0)]
    quantity_increment: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    partial_fills_supported: Literal[False] = False
    missing_data_policy: Literal[MissingExecutionDataPolicy.EXPIRE_UNFILLED] = (
        MissingExecutionDataPolicy.EXPIRE_UNFILLED
    )
    gap_policy: Literal[GapPolicy.USE_NEXT_ELIGIBLE_OPEN] = GapPolicy.USE_NEXT_ELIGIBLE_OPEN
    ambiguity_policy: Literal[IntrabarAmbiguityPolicy.STOP_FIRST] = (
        IntrabarAmbiguityPolicy.STOP_FIRST
    )
    randomness_policy: Literal[RandomnessPolicy.NONE] = RandomnessPolicy.NONE

    @field_validator("quantity_increment", mode="before")
    @classmethod
    def reject_float_quantity(cls, value: object) -> object:
        return _reject_float(value, "quantity increment")

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.execution_model_id != calculate_execution_model_id(self):
            raise ValueError("execution model identity does not match content")
        return self


def calculate_execution_model_id(
    configuration: SimulationExecutionConfiguration | dict[str, object],
) -> SimulationExecutionModelId:
    content = _normalized_decimal_content(
        configuration, "execution_model_id", ("quantity_increment",)
    )
    return SimulationExecutionModelId.parse(sha256_content_id_v2(content))


class ZeroVolumePolicy(StrEnum):
    """Conservative behavior when an eligible bar reports no executed volume."""

    REJECT_FULL_FILL = "REJECT_FULL_FILL"


class SimulationLiquidityConfiguration(BaseModel):
    """Immutable full-fill liquidity assumptions bound into V2 run identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    liquidity_model_id: SimulationLiquidityModelId
    schema_version: Literal["simulation-liquidity-v1"] = "simulation-liquidity-v1"
    model_version: str = Field(min_length=1)
    maximum_bar_volume_participation: Annotated[Decimal, Field(gt=0, le=1, allow_inf_nan=False)]
    zero_volume_policy: Literal[ZeroVolumePolicy.REJECT_FULL_FILL] = (
        ZeroVolumePolicy.REJECT_FULL_FILL
    )
    partial_fills_supported: Literal[False] = False

    @field_validator("maximum_bar_volume_participation", mode="before")
    @classmethod
    def reject_float_participation(cls, value: object) -> object:
        return _reject_float(value, "volume participation")

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.liquidity_model_id != calculate_liquidity_model_id(self):
            raise ValueError("simulation liquidity identity does not match content")
        return self


def calculate_liquidity_model_id(
    configuration: SimulationLiquidityConfiguration | dict[str, object],
) -> SimulationLiquidityModelId:
    content = _normalized_decimal_content(
        configuration,
        "liquidity_model_id",
        ("maximum_bar_volume_participation",),
    )
    return SimulationLiquidityModelId.parse(sha256_content_id_v2(content))


class TransactionCostConfiguration(BaseModel):
    """Versioned monetary cost inputs; numeric schedules remain experiment configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cost_model_id: TransactionCostModelId
    schema_version: Literal["transaction-cost-v1"] = "transaction-cost-v1"
    profile_name: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    minimum_commission_per_order: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    commission_per_share: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    spread_bps: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    slippage_bps: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    other_fee_bps: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]

    @field_validator(
        "minimum_commission_per_order",
        "commission_per_share",
        "spread_bps",
        "slippage_bps",
        "other_fee_bps",
        mode="before",
    )
    @classmethod
    def reject_float_costs(cls, value: object) -> object:
        return _reject_float(value, "transaction-cost value")

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.cost_model_id != calculate_cost_model_id(self):
            raise ValueError("transaction-cost model identity does not match content")
        return self


def calculate_cost_model_id(
    configuration: TransactionCostConfiguration | dict[str, object],
) -> TransactionCostModelId:
    content = _normalized_decimal_content(
        configuration,
        "cost_model_id",
        (
            "minimum_commission_per_order",
            "commission_per_share",
            "spread_bps",
            "slippage_bps",
            "other_fee_bps",
        ),
    )
    return TransactionCostModelId.parse(sha256_content_id_v2(content))


class FillCostBreakdown(BaseModel):
    """Auditable per-fill costs, separate from the causal bar-open fill price."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cost_model_id: TransactionCostModelId
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    reference_notional: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    commission: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    spread: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    slippage: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    other_fees: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    total: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]

    @field_validator(
        "reference_notional",
        "commission",
        "spread",
        "slippage",
        "other_fees",
        "total",
        mode="before",
    )
    @classmethod
    def reject_float_costs(cls, value: object) -> object:
        return _reject_float(value, "fill-cost value")

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
            expected = self.commission + self.spread + self.slippage + self.other_fees
        if self.total != expected:
            raise ValueError("fill cost total must equal all itemized components")
        return self


def calculate_fill_costs(
    configuration: TransactionCostConfiguration,
    quantity: Decimal,
    reference_price: Decimal,
) -> FillCostBreakdown:
    """Calculate exact, unrounded V1 monetary cost components for one fill."""
    if isinstance(quantity, float) or isinstance(reference_price, float):
        raise TypeError("fill-cost inputs must use Decimal, not float")
    if not quantity.is_finite() or quantity <= 0:
        raise ValueError("fill-cost quantity must be finite and positive")
    if not reference_price.is_finite() or reference_price <= 0:
        raise ValueError("fill-cost reference price must be finite and positive")
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        notional = quantity * reference_price
        commission = max(
            configuration.minimum_commission_per_order,
            configuration.commission_per_share * quantity,
        )
        basis_points = Decimal("10000")
        spread = notional * configuration.spread_bps / basis_points
        slippage = notional * configuration.slippage_bps / basis_points
        other_fees = notional * configuration.other_fee_bps / basis_points
        total = commission + spread + slippage + other_fees
    return FillCostBreakdown(
        cost_model_id=configuration.cost_model_id,
        currency=configuration.currency,
        reference_notional=notional,
        commission=commission,
        spread=spread,
        slippage=slippage,
        other_fees=other_fees,
        total=total,
    )


class SimulationRunManifest(BaseModel):
    """All immutable inputs that determine one isolated participant replay."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: SimulationRunId
    schema_version: Literal["simulation-run-manifest-v1", "simulation-run-manifest-v2"] = (
        "simulation-run-manifest-v1"
    )
    dataset_id: DatasetId
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    strategy_id: StrategyId
    strategy_configuration_id: StrategyConfigurationId
    strategy_version: str = Field(min_length=1)
    model_id: ModelId | None = None
    indicator_configuration_ids: tuple[IndicatorConfigurationId, ...] = Field(min_length=1)
    risk_configuration_id: RiskConfigurationId
    management_mandate_id: ManagementMandateId
    configuration_version_id: ConfigurationVersionId
    execution_model_id: SimulationExecutionModelId
    cost_model_id: TransactionCostModelId
    liquidity_configuration: SimulationLiquidityConfiguration | None = None
    replay_tie_break_policy: Literal[ReplayTieBreakPolicy.SEMANTIC_PAYLOAD_V1] = (
        ReplayTieBreakPolicy.SEMANTIC_PAYLOAD_V1
    )
    starting_capital: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    reporting_currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    execution_dimensions: ExecutionDimensions
    random_seed: Literal[None] = None

    @field_validator("starting_capital", mode="before")
    @classmethod
    def reject_float_capital(cls, value: object) -> object:
        return _reject_float(value, "starting capital")

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if (self.schema_version == "simulation-run-manifest-v2") != (
            self.liquidity_configuration is not None
        ):
            raise ValueError(
                "V2 run manifests require liquidity configuration and V1 manifests forbid it"
            )
        if self.execution_dimensions.execution_environment is not ExecutionEnvironment.SIMULATION:
            raise ValueError("Phase 6 run manifests permit SIMULATION only")
        if self.execution_dimensions.data_run_mode not in {
            DataRunMode.HISTORICAL_REPLAY,
            DataRunMode.CAPTURED_REPLAY,
        }:
            raise ValueError("Phase 6 run manifests require historical or captured replay")
        if tuple(sorted(self.indicator_configuration_ids, key=str)) != (
            self.indicator_configuration_ids
        ) or len(set(self.indicator_configuration_ids)) != len(self.indicator_configuration_ids):
            raise ValueError("indicator configuration identities must be sorted and unique")
        if self.run_id != calculate_simulation_run_id(self):
            raise ValueError("simulation run identity does not match manifest content")
        return self


def calculate_simulation_run_id(
    manifest: SimulationRunManifest | dict[str, object],
) -> SimulationRunId:
    content = _normalized_decimal_content(manifest, "run_id", ("starting_capital",))
    content.setdefault("replay_tie_break_policy", ReplayTieBreakPolicy.SEMANTIC_PAYLOAD_V1)
    if content.get("schema_version", "simulation-run-manifest-v1") == (
        "simulation-run-manifest-v1"
    ):
        # Preserve all accepted V1 run identities after adding the optional V2 field.
        content.pop("liquidity_configuration", None)
    return SimulationRunId.parse(sha256_content_id_v2(content))


class SimulatedOrder(BaseModel):
    """Immutable provider-neutral order intent accepted by the offline simulator."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: SimulatedOrderId
    schema_version: Literal["simulated-order-v1"] = "simulated-order-v1"
    run_id: SimulationRunId
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    strategy_id: StrategyId
    management_mandate_id: ManagementMandateId
    proposal_id: TradeProposalId
    strategy_decision_id: StrategyDecisionId
    risk_decision_id: RiskDecisionId
    reservation_id: ReservationId
    instrument_id: InstrumentId
    side: SimulatedOrderSide
    order_type: Literal[SimulatedOrderType.MARKET] = SimulatedOrderType.MARKET
    quantity: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    execution_model_id: SimulationExecutionModelId
    decision_at: datetime
    submitted_at: datetime
    eligible_at: datetime
    valid_until: datetime

    @field_validator("quantity", mode="before")
    @classmethod
    def reject_float_quantity(cls, value: object) -> object:
        return _reject_float(value, "order quantity")

    @field_validator("decision_at", "submitted_at", "eligible_at", "valid_until")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.submitted_at < self.decision_at:
            raise ValueError("order submission cannot predate its decision")
        if self.eligible_at < self.submitted_at:
            raise ValueError("order eligibility cannot predate submission")
        if self.valid_until <= self.eligible_at:
            raise ValueError("order validity must extend beyond eligibility")
        if self.order_id != calculate_simulated_order_id(self):
            raise ValueError("simulated order identity does not match content")
        return self


def calculate_simulated_order_id(order: SimulatedOrder | dict[str, object]) -> SimulatedOrderId:
    content = _normalized_decimal_content(order, "order_id", ("quantity",))
    return SimulatedOrderId.parse(sha256_content_id_v2(content))


class SimulatedFill(BaseModel):
    """Deterministic full fill produced by a future eligible market interval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fill_id: SimulatedFillId
    schema_version: Literal["simulated-fill-v1"] = "simulated-fill-v1"
    run_id: SimulationRunId
    order_id: SimulatedOrderId
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    proposal_id: TradeProposalId
    risk_decision_id: RiskDecisionId
    reservation_id: ReservationId
    instrument_id: InstrumentId
    side: SimulatedOrderSide
    quantity: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    fill_price: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    execution_model_id: SimulationExecutionModelId
    market_event: MarketEventReference
    submitted_at: datetime
    eligible_at: datetime
    execution_interval_start_at: datetime
    execution_interval_end_at: datetime
    simulated_execution_at: datetime
    fill_at: datetime
    costs: FillCostBreakdown

    @field_validator("quantity", "fill_price", mode="before")
    @classmethod
    def reject_float_financials(cls, value: object) -> object:
        return _reject_float(value, "fill financial value")

    @field_validator(
        "submitted_at",
        "eligible_at",
        "execution_interval_start_at",
        "execution_interval_end_at",
        "simulated_execution_at",
        "fill_at",
    )
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_fill(self) -> Self:
        if self.eligible_at < self.submitted_at:
            raise ValueError("fill eligibility cannot predate submission")
        if self.execution_interval_start_at <= self.eligible_at:
            raise ValueError("execution interval open must be strictly later than eligibility")
        if self.execution_interval_end_at <= self.execution_interval_start_at:
            raise ValueError("execution interval end must follow its start")
        if self.simulated_execution_at != self.execution_interval_start_at:
            raise ValueError("V1 market fills execute at the eligible interval open")
        if (
            self.market_event.interval_start_at != self.execution_interval_start_at
            or self.market_event.event_at != self.execution_interval_end_at
            or self.market_event.instrument_id != self.instrument_id
        ):
            raise ValueError("fill interval must match its market-event lineage")
        if self.fill_at < self.market_event.available_at:
            raise ValueError("fill cannot be recorded before its price source is available")
        if self.costs.currency != self.currency:
            raise ValueError("fill and cost currencies differ")
        with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
            expected_notional = self.quantity * self.fill_price
        if self.costs.reference_notional != expected_notional:
            raise ValueError("fill costs do not match quantity times fill price")
        if self.fill_id != calculate_simulated_fill_id(self):
            raise ValueError("simulated fill identity does not match content")
        return self


def calculate_simulated_fill_id(fill: SimulatedFill | dict[str, object]) -> SimulatedFillId:
    content = _normalized_decimal_content(fill, "fill_id", ("quantity", "fill_price"))
    return SimulatedFillId.parse(sha256_content_id_v2(content))


def validate_fill_against_order(fill: SimulatedFill, order: SimulatedOrder) -> None:
    """Fail if a V1 fill is not an exact, full causal realization of its order."""
    linked = (
        fill.run_id == order.run_id
        and fill.order_id == order.order_id
        and fill.account_id == order.account_id
        and fill.allocation_id == order.allocation_id
        and fill.agent_id == order.agent_id
        and fill.proposal_id == order.proposal_id
        and fill.risk_decision_id == order.risk_decision_id
        and fill.reservation_id == order.reservation_id
        and fill.instrument_id == order.instrument_id
        and fill.side == order.side
        and fill.currency == order.currency
        and fill.execution_model_id == order.execution_model_id
    )
    if not linked:
        raise ValueError("fill attribution or immutable order linkage differs")
    if fill.quantity != order.quantity:
        raise ValueError("V1 does not support partial fills")
    if fill.submitted_at != order.submitted_at or fill.eligible_at != order.eligible_at:
        raise ValueError("fill causal order timestamps differ")
    if fill.execution_interval_start_at >= order.valid_until:
        raise ValueError("fill execution starts after order expiry")


class ReplayEvent(BaseModel):
    """Content-identified event envelope with an explicit deterministic ordering key."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    replay_event_id: ReplayEventId
    schema_version: Literal["replay-event-v1"] = "replay-event-v1"
    run_id: SimulationRunId
    scheduled_at: datetime
    phase: ReplayPhase
    tie_break_policy: Literal[ReplayTieBreakPolicy.SEMANTIC_PAYLOAD_V1] = (
        ReplayTieBreakPolicy.SEMANTIC_PAYLOAD_V1
    )
    payload_kind: ReplayPayloadKind
    payload_id: str = Field(min_length=1, max_length=256)

    @field_validator("scheduled_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.payload_id != self.payload_id.strip():
            raise ValueError("payload identity cannot contain surrounding whitespace")
        allowed_payloads = {
            ReplayPhase.EXECUTION_RESOLUTION: {ReplayPayloadKind.EXECUTION_RESOLUTION},
            ReplayPhase.FILL: {ReplayPayloadKind.SIMULATED_FILL},
            ReplayPhase.PORTFOLIO_UPDATE: {
                ReplayPayloadKind.POSITION_CHANGE,
                ReplayPayloadKind.PORTFOLIO_SNAPSHOT,
                ReplayPayloadKind.REALIZED_TRADE,
            },
            ReplayPhase.SESSION_CONTROL: {ReplayPayloadKind.SESSION_CONTROL},
            ReplayPhase.MARKET_DATA_AVAILABLE: {ReplayPayloadKind.MARKET_EVENT},
            ReplayPhase.INDICATOR_UPDATE: {ReplayPayloadKind.INDICATOR_UPDATE},
            ReplayPhase.STRATEGY_EVALUATION: {ReplayPayloadKind.STRATEGY_DECISION},
            ReplayPhase.RISK_EVALUATION: {ReplayPayloadKind.RISK_DECISION},
            ReplayPhase.ORDER_SUBMISSION: {ReplayPayloadKind.SIMULATED_ORDER},
            ReplayPhase.RESULT_FINALIZATION: {ReplayPayloadKind.RUN_RESULT},
        }
        if self.payload_kind not in allowed_payloads[self.phase]:
            raise ValueError("replay payload kind is incompatible with causal phase")
        if self.replay_event_id != calculate_replay_event_id(self):
            raise ValueError("replay event identity does not match content")
        return self

    @property
    def ordering_key(self) -> tuple[datetime, int, str]:
        dependency_rank = _SEMANTIC_PAYLOAD_KIND_RANK_V1.get(self.payload_kind, 0)
        semantic_key = f"{dependency_rank:03d}:{self.payload_kind.value}:{self.payload_id}"
        return (self.scheduled_at, int(self.phase), semantic_key)


def calculate_replay_event_id(event: ReplayEvent | dict[str, object]) -> ReplayEventId:
    content = _identity_content(event, "replay_event_id")
    content.setdefault("tie_break_policy", ReplayTieBreakPolicy.SEMANTIC_PAYLOAD_V1)
    return ReplayEventId.parse(sha256_content_id_v2(content))


def order_replay_events(events: tuple[ReplayEvent, ...]) -> tuple[ReplayEvent, ...]:
    """Derive the one canonical order; callers cannot supply ordering semantics."""
    ordered = tuple(sorted(events, key=lambda event: event.ordering_key))
    validate_replay_trace(ordered)
    return ordered


def validate_replay_trace(events: tuple[ReplayEvent, ...]) -> None:
    """Require one run, unique identities/keys, and canonical strict ordering."""
    if not events:
        raise ValueError("replay trace requires at least one event")
    if len({event.run_id for event in events}) != 1:
        raise ValueError("replay trace cannot mix run identities")
    if len({event.replay_event_id for event in events}) != len(events):
        raise ValueError("replay trace contains duplicate event identities")
    keys = tuple(event.ordering_key for event in events)
    if len(set(keys)) != len(keys):
        raise ValueError("replay trace contains duplicate ordering keys")
    if keys != tuple(sorted(keys)):
        raise ValueError("replay trace is not in canonical event order")


def serialize_replay_events(events: tuple[ReplayEvent, ...]) -> bytes:
    """Return canonical UTF-8 NDJSON bytes suitable for a local replay artifact."""
    validate_replay_trace(events)
    return b"".join(canonical_json_bytes_v2(event) + b"\n" for event in events)


def calculate_replay_trace_hash(events: tuple[ReplayEvent, ...]) -> str:
    return hashlib.sha256(serialize_replay_events(events)).hexdigest()
