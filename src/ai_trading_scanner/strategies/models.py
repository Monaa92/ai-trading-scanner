"""Immutable strategy evaluation, decision, and trade-proposal contracts."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_trading_scanner.domain import (
    AgentId,
    ConfigurationVersionId,
    DatasetId,
    IndicatorConfigurationId,
    InstrumentId,
    ManagementMandateId,
    StrategyConfigurationId,
    StrategyDecisionId,
    StrategyId,
    TradeProposalId,
)
from ai_trading_scanner.domain.content_identity import canonical_json_bytes, sha256_content_id
from ai_trading_scanner.domain.execution import ExecutionDimensions
from ai_trading_scanner.indicators import (
    ATRConfig,
    EMAConfig,
    IndicatorReason,
    IndicatorSeries,
    RSIConfig,
    VWAPConfig,
)
from ai_trading_scanner.market_data import (
    MarketDataSlice,
    QualityFinding,
)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


class StrategyOutcome(StrEnum):
    NO_TRADE = "NO_TRADE"
    TRADE_PROPOSAL = "TRADE_PROPOSAL"


class NoTradeReason(StrEnum):
    INSUFFICIENT_SIGNAL = "INSUFFICIENT_SIGNAL"
    INSUFFICIENT_CONFIRMATION = "INSUFFICIENT_CONFIRMATION"
    CONFLICTING_FACTORS = "CONFLICTING_FACTORS"
    UNSUITABLE_REGIME = "UNSUITABLE_REGIME"
    DATA_QUALITY_CONCERN = "DATA_QUALITY_CONCERN"
    INDICATOR_NOT_READY = "INDICATOR_NOT_READY"
    GAP_OR_INCOMPLETE_SESSION = "GAP_OR_INCOMPLETE_SESSION"
    EXPECTED_EDGE_TOO_SMALL = "EXPECTED_EDGE_TOO_SMALL"
    TRANSACTION_COST_CONCERN = "TRANSACTION_COST_CONCERN"
    STRATEGY_INVALIDATED = "STRATEGY_INVALIDATED"
    UNSUPPORTED_CONTEXT = "UNSUPPORTED_CONTEXT"
    UNAUTHORIZED_DIRECTION = "UNAUTHORIZED_DIRECTION"


class EvidenceValueType(StrEnum):
    BOOLEAN = "BOOLEAN"
    DECIMAL = "DECIMAL"
    TEXT = "TEXT"


class EvidenceItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    value_type: EvidenceValueType
    value: bool | Decimal | str
    unit: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_typed_value(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        value = data.get("value")
        if isinstance(value, float):
            raise ValueError("evidence values must not use float")
        value_type = data.get("value_type")
        decimal_types = {
            EvidenceValueType.DECIMAL,
            EvidenceValueType.DECIMAL.value,
        }
        if value_type in decimal_types and isinstance(value, str):
            return {**data, "value": Decimal(value)}
        return data

    @model_validator(mode="after")
    def validate_value_type(self) -> Self:
        valid = (
            (self.value_type is EvidenceValueType.BOOLEAN and isinstance(self.value, bool))
            or (
                self.value_type is EvidenceValueType.DECIMAL
                and isinstance(self.value, Decimal)
                and not isinstance(self.value, bool)
            )
            or (self.value_type is EvidenceValueType.TEXT and isinstance(self.value, str))
        )
        if not valid:
            raise ValueError("evidence value does not match value_type")
        if isinstance(self.value, Decimal) and not self.value.is_finite():
            raise ValueError("decimal evidence must be finite")
        return self


class RoundTripCostEstimate(BaseModel):
    """Externally supplied normalized estimate; never a broker fee schedule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    methodology_version_id: ConfigurationVersionId
    entry_cost_return: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    exit_cost_return: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    spread_return: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    slippage_return: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    other_execution_cost_return: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)] = Decimal(0)

    @field_validator(
        "entry_cost_return",
        "exit_cost_return",
        "spread_return",
        "slippage_return",
        "other_execution_cost_return",
        mode="before",
    )
    @classmethod
    def reject_float(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("cost estimates must not use float")
        return value

    @property
    def total_return_drag(self) -> Decimal:
        with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
            return (
                self.entry_cost_return
                + self.exit_cost_return
                + self.spread_return
                + self.slippage_return
                + self.other_execution_cost_return
            )


class IndicatorSnapshot(BaseModel):
    """The common Phase 3 information family offered to every strategy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ema_fast: IndicatorSeries
    ema_medium: IndicatorSeries
    ema_slow: IndicatorSeries
    rsi: IndicatorSeries
    atr: IndicatorSeries
    session_vwap: IndicatorSeries

    @model_validator(mode="after")
    def validate_common_lineage_and_types(self) -> Self:
        series = self.all_series
        first = series[0]
        if any(
            item.dataset_id != first.dataset_id
            or item.input_slice_hash_sha256 != first.input_slice_hash_sha256
            or item.as_of != first.as_of
            for item in series[1:]
        ):
            raise ValueError("indicator snapshot series must share causal input lineage")
        if not all(isinstance(item.configuration, EMAConfig) for item in series[:3]):
            raise ValueError("ema_fast/medium/slow must contain EMA series")
        if not isinstance(self.rsi.configuration, RSIConfig):
            raise ValueError("rsi must contain an RSI series")
        if not isinstance(self.atr.configuration, ATRConfig):
            raise ValueError("atr must contain an ATR series")
        if not isinstance(self.session_vwap.configuration, VWAPConfig):
            raise ValueError("session_vwap must contain a VWAP series")
        return self

    @property
    def all_series(self) -> tuple[IndicatorSeries, ...]:
        return (
            self.ema_fast,
            self.ema_medium,
            self.ema_slow,
            self.rsi,
            self.atr,
            self.session_vwap,
        )

    @property
    def configuration_ids(self) -> tuple[IndicatorConfigurationId, ...]:
        return tuple(sorted((item.configuration_id for item in self.all_series), key=str))


class ProposalAuthorityContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    configuration_version_id: ConfigurationVersionId
    execution_dimensions: ExecutionDimensions


class StrategyEvaluationContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: AgentId
    strategy_id: StrategyId
    strategy_configuration_id: StrategyConfigurationId
    instrument_id: InstrumentId
    as_of: datetime
    market_data: MarketDataSlice
    indicators: IndicatorSnapshot
    cost_estimate: RoundTripCostEstimate | None = None
    authority_context: ProposalAuthorityContext

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_causal_lineage(self) -> Self:
        if self.as_of != self.market_data.as_of or self.as_of != self.indicators.ema_fast.as_of:
            raise ValueError("context and all causal inputs must share as_of")
        if self.market_data.dataset_id != self.indicators.ema_fast.dataset_id:
            raise ValueError("market and indicator dataset identity differs")
        if self.market_data.content_hash_sha256 != self.indicators.ema_fast.input_slice_hash_sha256:
            raise ValueError("market and indicator slice identity differs")
        if not self.market_data.bars:
            raise ValueError("strategy evaluation requires at least one causal bar")
        if any(bar.instrument_id != self.instrument_id for bar in self.market_data.bars):
            raise ValueError("strategy context contains a different instrument")
        if any(bar.available_at > self.as_of for bar in self.market_data.bars):
            raise ValueError("strategy context contains future-unavailable market data")
        if any(
            finding.end_at is not None and finding.end_at > self.as_of
            for finding in self.market_data.quality_findings
        ):
            raise ValueError("strategy context contains a future quality finding")
        expected_hash = hashlib.sha256(canonical_json_bytes(self.market_data.bars)).hexdigest()
        if self.market_data.content_hash_sha256 != expected_hash:
            raise ValueError("market-data slice identity does not match causal bars")
        for series in self.indicators.all_series:
            if series.quality_findings != self.market_data.quality_findings:
                raise ValueError("indicator quality lineage differs from market-data slice")
            if any(point.instrument_id != self.instrument_id for point in series.points):
                raise ValueError("strategy context contains a different indicator instrument")
            point_lineage = tuple(
                (
                    point.instrument_id,
                    point.timeframe,
                    point.session_id,
                    point.bar_start_at,
                    point.bar_end_at,
                    point.bar_available_at,
                )
                for point in series.points
            )
            bar_lineage = tuple(
                (
                    bar.instrument_id,
                    bar.timeframe,
                    bar.session_id,
                    bar.start_at,
                    bar.end_at,
                    bar.available_at,
                )
                for bar in self.market_data.bars
            )
            if point_lineage != bar_lineage:
                raise ValueError("indicator points do not align with causal market bars")
        return self


class ProposalSide(StrEnum):
    LONG = "LONG"


class EntryReferenceMethod(StrEnum):
    COMPLETED_BAR_CLOSE = "COMPLETED_BAR_CLOSE"


class EntryIntent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reference_method: Literal[EntryReferenceMethod.COMPLETED_BAR_CLOSE] = (
        EntryReferenceMethod.COMPLETED_BAR_CLOSE
    )
    reference_price: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")

    @field_validator("reference_price", mode="before")
    @classmethod
    def reject_float(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("entry reference must not use float")
        return value


class SizingMethod(StrEnum):
    FUTURE_RISK_ENGINE = "FUTURE_RISK_ENGINE"
    FINAL_QUANTITY = "FINAL_QUANTITY"


class SizingIntent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    method: SizingMethod = SizingMethod.FUTURE_RISK_ENGINE
    final_quantity: Annotated[Decimal | None, Field(gt=0, allow_inf_nan=False)] = None

    @field_validator("final_quantity", mode="before")
    @classmethod
    def reject_float(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("quantity must not use float")
        return value

    @model_validator(mode="after")
    def validate_method(self) -> Self:
        if self.method is SizingMethod.FUTURE_RISK_ENGINE and self.final_quantity is not None:
            raise ValueError("future risk-engine sizing cannot claim a final quantity")
        if self.method is SizingMethod.FINAL_QUANTITY and self.final_quantity is None:
            raise ValueError("final-quantity sizing requires a quantity")
        return self


class ObjectiveKind(StrEnum):
    RESISTANCE_LEVEL = "RESISTANCE_LEVEL"
    REVERSION_LEVEL = "REVERSION_LEVEL"
    BREAKOUT_CONTINUATION = "BREAKOUT_CONTINUATION"
    MULTI_FACTOR_THESIS = "MULTI_FACTOR_THESIS"


class ObjectiveIntent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ObjectiveKind
    reference_level: Annotated[Decimal | None, Field(gt=0, allow_inf_nan=False)] = None
    is_mandatory_exit: bool = False

    @field_validator("reference_level", mode="before")
    @classmethod
    def reject_float(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("objective level must not use float")
        return value

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        if (
            self.kind in {ObjectiveKind.RESISTANCE_LEVEL, ObjectiveKind.REVERSION_LEVEL}
            and self.reference_level is None
        ):
            raise ValueError("level-based objective requires reference_level")
        return self


class ManagementStyle(StrEnum):
    MOMENTUM_TREND = "MOMENTUM_TREND"
    MEAN_REVERSION = "MEAN_REVERSION"
    BREAKOUT_CONTINUATION = "BREAKOUT_CONTINUATION"
    MULTI_FACTOR_DYNAMIC = "MULTI_FACTOR_DYNAMIC"


class ManagementTrigger(StrEnum):
    PROTECTIVE_STOP = "PROTECTIVE_STOP"
    TARGET_REACHED = "TARGET_REACHED"
    TREND_INVALIDATED = "TREND_INVALIDATED"
    MOMENTUM_DETERIORATED = "MOMENTUM_DETERIORATED"
    TRAILING_PROTECTION = "TRAILING_PROTECTION"
    MEAN_REACHED = "MEAN_REACHED"
    THESIS_INVALIDATED = "THESIS_INVALIDATED"
    BREAKOUT_FAILED = "BREAKOUT_FAILED"
    RANGE_REENTRY = "RANGE_REENTRY"
    FACTORS_DETERIORATED = "FACTORS_DETERIORATED"


class ManagementMandate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mandate_id: ManagementMandateId
    schema_version: Literal["management-mandate-v1"] = "management-mandate-v1"
    style: ManagementStyle
    triggers: tuple[ManagementTrigger, ...] = Field(min_length=2)
    protective_stop_required: Literal[True] = True
    universal_profit_cap: Literal[False] = False

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if len(set(self.triggers)) != len(self.triggers):
            raise ValueError("management triggers must be unique")
        if tuple(sorted(self.triggers, key=lambda trigger: trigger.value)) != self.triggers:
            raise ValueError("management triggers must use canonical order")
        if self.mandate_id != calculate_management_mandate_id(self):
            raise ValueError("management mandate identity does not match content")
        return self


def calculate_management_mandate_id(
    mandate: ManagementMandate | dict[str, object],
) -> ManagementMandateId:
    if isinstance(mandate, BaseModel):
        content = mandate.model_dump(mode="python", exclude={"mandate_id"})
    else:
        content = {key: value for key, value in mandate.items() if key != "mandate_id"}
    return ManagementMandateId.parse(sha256_content_id(content))


def create_management_mandate(
    style: ManagementStyle, triggers: tuple[ManagementTrigger, ...]
) -> ManagementMandate:
    ordered = tuple(sorted(set(triggers), key=lambda trigger: trigger.value))
    content: dict[str, object] = {
        "schema_version": "management-mandate-v1",
        "style": style,
        "triggers": ordered,
        "protective_stop_required": True,
        "universal_profit_cap": False,
    }
    return ManagementMandate(
        mandate_id=calculate_management_mandate_id(content),
        **content,  # type: ignore[arg-type]
    )


class ExpectedEconomics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gross_expected_return: Annotated[Decimal, Field(allow_inf_nan=False)]
    cost_estimate: RoundTripCostEstimate
    net_expected_return: Annotated[Decimal, Field(allow_inf_nan=False)]

    @field_validator("gross_expected_return", "net_expected_return", mode="before")
    @classmethod
    def reject_float(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("expected economics must not use float")
        return value

    @model_validator(mode="after")
    def validate_net(self) -> Self:
        with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
            expected = self.gross_expected_return - self.cost_estimate.total_return_drag
            if self.net_expected_return != expected:
                raise ValueError("net expected return must equal gross return minus all costs")
        return self


class TradeProposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    proposal_id: TradeProposalId
    schema_version: Literal["trade-proposal-v1"] = "trade-proposal-v1"
    agent_id: AgentId
    strategy_id: StrategyId
    strategy_version: str
    strategy_configuration_id: StrategyConfigurationId
    instrument_id: InstrumentId
    side: Literal[ProposalSide.LONG] = ProposalSide.LONG
    generated_at: datetime
    as_of: datetime
    valid_until: datetime
    dataset_id: DatasetId
    market_data_slice_hash_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    indicator_configuration_ids: tuple[IndicatorConfigurationId, ...] = Field(min_length=1)
    entry: EntryIntent
    sizing: SizingIntent
    stop_level: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    objective: ObjectiveIntent
    management_mandate: ManagementMandate
    economics: ExpectedEconomics
    evidence: tuple[EvidenceItem, ...] = Field(min_length=1)
    quality_findings: tuple[QualityFinding, ...]
    authority_context: ProposalAuthorityContext

    @field_validator("generated_at", "as_of", "valid_until")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @field_validator("stop_level", mode="before")
    @classmethod
    def reject_float_stop(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("stop level must not use float")
        return value

    @model_validator(mode="after")
    def validate_proposal(self) -> Self:
        if self.generated_at != self.as_of:
            raise ValueError("deterministic proposal generated_at must equal causal as_of")
        if self.valid_until <= self.as_of:
            raise ValueError("proposal validity must end after as_of")
        if self.stop_level >= self.entry.reference_price:
            raise ValueError("long proposal stop must be below entry reference")
        if tuple(sorted(self.indicator_configuration_ids, key=str)) != (
            self.indicator_configuration_ids
        ):
            raise ValueError("indicator configuration identities must use canonical order")
        if len(set(self.indicator_configuration_ids)) != len(self.indicator_configuration_ids):
            raise ValueError("indicator configuration identities must be unique")
        if len({item.name for item in self.evidence}) != len(self.evidence):
            raise ValueError("proposal evidence names must be unique")
        if self.proposal_id != calculate_trade_proposal_id(self):
            raise ValueError("trade proposal identity does not match approval-sensitive content")
        return self


def calculate_trade_proposal_id(proposal: TradeProposal | dict[str, object]) -> TradeProposalId:
    if isinstance(proposal, BaseModel):
        content = proposal.model_dump(mode="python", exclude={"proposal_id"})
    else:
        content = {key: value for key, value in proposal.items() if key != "proposal_id"}
    return TradeProposalId.parse(sha256_content_id(content))


class _DecisionBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: StrategyDecisionId
    schema_version: Literal["strategy-decision-v1"] = "strategy-decision-v1"
    agent_id: AgentId
    strategy_id: StrategyId
    strategy_version: str
    strategy_configuration_id: StrategyConfigurationId
    instrument_id: InstrumentId
    as_of: datetime
    dataset_id: DatasetId
    market_data_slice_hash_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    indicator_configuration_ids: tuple[IndicatorConfigurationId, ...] = Field(min_length=1)
    evidence: tuple[EvidenceItem, ...] = Field(min_length=1)
    quality_findings: tuple[QualityFinding, ...]

    @field_validator("as_of")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)


class NoTradeDecision(_DecisionBase):
    outcome: Literal[StrategyOutcome.NO_TRADE] = StrategyOutcome.NO_TRADE
    reasons: tuple[NoTradeReason, ...] = Field(min_length=1)
    detail: str | None = None
    proposal: Literal[None] = None

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("NO_TRADE reasons must be unique")
        if tuple(sorted(self.reasons, key=lambda reason: reason.value)) != self.reasons:
            raise ValueError("NO_TRADE reasons must use canonical order")
        if self.decision_id != calculate_strategy_decision_id(self):
            raise ValueError("strategy decision identity does not match content")
        return self


class TradeProposalDecision(_DecisionBase):
    outcome: Literal[StrategyOutcome.TRADE_PROPOSAL] = StrategyOutcome.TRADE_PROPOSAL
    reasons: tuple[()] = ()
    detail: str | None = None
    proposal: TradeProposal

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if (
            self.agent_id != self.proposal.agent_id
            or self.strategy_id != self.proposal.strategy_id
            or self.strategy_version != self.proposal.strategy_version
            or self.strategy_configuration_id != self.proposal.strategy_configuration_id
            or self.instrument_id != self.proposal.instrument_id
            or self.as_of != self.proposal.as_of
            or self.dataset_id != self.proposal.dataset_id
            or self.market_data_slice_hash_sha256 != self.proposal.market_data_slice_hash_sha256
            or self.indicator_configuration_ids != self.proposal.indicator_configuration_ids
            or self.evidence != self.proposal.evidence
            or self.quality_findings != self.proposal.quality_findings
        ):
            raise ValueError("decision and proposal attribution or lineage differs")
        if self.decision_id != calculate_strategy_decision_id(self):
            raise ValueError("strategy decision identity does not match content")
        return self


StrategyDecision = Annotated[
    NoTradeDecision | TradeProposalDecision, Field(discriminator="outcome")
]


def calculate_strategy_decision_id(
    decision: NoTradeDecision | TradeProposalDecision | dict[str, object],
) -> StrategyDecisionId:
    if isinstance(decision, BaseModel):
        content = decision.model_dump(mode="python", exclude={"decision_id"})
    else:
        content = {key: value for key, value in decision.items() if key != "decision_id"}
    return StrategyDecisionId.parse(sha256_content_id(content))


def latest_indicator_value(series: IndicatorSeries) -> Decimal | None:
    point = series.points[-1]
    return point.value if point.ready and point.reason is IndicatorReason.READY else None
