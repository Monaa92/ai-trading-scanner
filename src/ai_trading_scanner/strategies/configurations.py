"""Registered, versioned research baseline strategy configurations."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_trading_scanner.domain import StrategyConfigurationId, StrategyId
from ai_trading_scanner.domain.content_identity import sha256_content_id
from ai_trading_scanner.market_data import Timeframe

BASELINE_RESEARCH_V1: Literal["BASELINE_RESEARCH_V1"] = "BASELINE_RESEARCH_V1"


class StrategyProfile(StrEnum):
    MOMENTUM_TREND_FOLLOWING = "MOMENTUM_TREND_FOLLOWING"
    MEAN_REVERSION = "MEAN_REVERSION"
    BREAKOUT_VOLATILITY = "BREAKOUT_VOLATILITY"
    MULTI_FACTOR_OPPORTUNISTIC = "MULTI_FACTOR_OPPORTUNISTIC"


MOMENTUM_STRATEGY_ID = StrategyId.parse("strategy:momentum-trend-following")
MEAN_REVERSION_STRATEGY_ID = StrategyId.parse("strategy:mean-reversion")
BREAKOUT_STRATEGY_ID = StrategyId.parse("strategy:breakout-volatility")
MULTI_FACTOR_STRATEGY_ID = StrategyId.parse("strategy:multi-factor-opportunistic")

PositivePeriod = Annotated[int, Field(strict=True, gt=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
PositiveDecimal = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]


class _StrategyConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["strategy-configuration-v1"] = "strategy-configuration-v1"
    baseline_name: Literal["BASELINE_RESEARCH_V1"] = BASELINE_RESEARCH_V1
    strategy_version: Literal["0.1.0"] = "0.1.0"
    timeframe: Literal[Timeframe.MINUTE_5] = Timeframe.MINUTE_5
    ema_fast_period: PositivePeriod = 9
    ema_medium_period: PositivePeriod = 20
    ema_slow_period: PositivePeriod = 50
    rsi_period: PositivePeriod = 14
    atr_period: PositivePeriod = 14
    maximum_data_age_seconds: Annotated[int, Field(strict=True, ge=0)] = 60
    proposal_validity_intervals: PositivePeriod = 2
    minimum_expected_net_return: NonNegativeDecimal = Decimal("0.001")

    @model_validator(mode="before")
    @classmethod
    def reject_any_float_parameter(cls, data: object) -> object:
        if isinstance(data, dict) and any(isinstance(value, float) for value in data.values()):
            raise ValueError("strategy decimal parameters must not use float")
        return data

    @field_validator("minimum_expected_net_return", mode="before")
    @classmethod
    def reject_float_decimal(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("strategy decimal parameters must not use float")
        return value

    @model_validator(mode="after")
    def validate_ema_order(self) -> Self:
        if not self.ema_fast_period < self.ema_medium_period < self.ema_slow_period:
            raise ValueError("EMA periods must be strictly increasing")
        return self


class MomentumConfiguration(_StrategyConfiguration):
    profile: Literal[StrategyProfile.MOMENTUM_TREND_FOLLOWING] = (
        StrategyProfile.MOMENTUM_TREND_FOLLOWING
    )
    strategy_id: StrategyId = MOMENTUM_STRATEGY_ID
    pullback_lookback: PositivePeriod = 5
    resistance_lookback: PositivePeriod = 20
    confirmation_bars: PositivePeriod = 1
    stop_atr_buffer: NonNegativeDecimal = Decimal("0.25")
    minimum_rsi: NonNegativeDecimal = Decimal("50")
    maximum_rsi: PositiveDecimal = Decimal("80")

    @model_validator(mode="after")
    def validate_momentum(self) -> Self:
        if self.strategy_id != MOMENTUM_STRATEGY_ID:
            raise ValueError("momentum configuration has the wrong strategy identity")
        if self.minimum_rsi >= self.maximum_rsi or self.maximum_rsi > 100:
            raise ValueError("momentum RSI bounds must satisfy 0 <= minimum < maximum <= 100")
        return self


class MeanReversionConfiguration(_StrategyConfiguration):
    profile: Literal[StrategyProfile.MEAN_REVERSION] = StrategyProfile.MEAN_REVERSION
    strategy_id: StrategyId = MEAN_REVERSION_STRATEGY_ID
    deviation_atr_multiple: PositiveDecimal = Decimal("1.5")
    oversold_rsi: NonNegativeDecimal = Decimal("30")
    confirmation_bars: PositivePeriod = 1
    stop_atr_multiple: PositiveDecimal = Decimal("1")

    @model_validator(mode="after")
    def validate_mean_reversion(self) -> Self:
        if self.strategy_id != MEAN_REVERSION_STRATEGY_ID:
            raise ValueError("mean-reversion configuration has the wrong strategy identity")
        if self.oversold_rsi > 100:
            raise ValueError("oversold RSI must not exceed 100")
        return self


class BreakoutConfiguration(_StrategyConfiguration):
    profile: Literal[StrategyProfile.BREAKOUT_VOLATILITY] = StrategyProfile.BREAKOUT_VOLATILITY
    strategy_id: StrategyId = BREAKOUT_STRATEGY_ID
    range_lookback: PositivePeriod = 20
    confirmation_bars: Annotated[int, Field(strict=True, ge=2)] = 2
    minimum_volume_multiple: PositiveDecimal = Decimal("1.2")
    stop_atr_buffer: NonNegativeDecimal = Decimal("0.25")
    expected_move_atr_multiple: PositiveDecimal = Decimal("2")

    @model_validator(mode="after")
    def validate_breakout(self) -> Self:
        if self.strategy_id != BREAKOUT_STRATEGY_ID:
            raise ValueError("breakout configuration has the wrong strategy identity")
        return self


class MultiFactorConfiguration(_StrategyConfiguration):
    profile: Literal[StrategyProfile.MULTI_FACTOR_OPPORTUNISTIC] = (
        StrategyProfile.MULTI_FACTOR_OPPORTUNISTIC
    )
    strategy_id: StrategyId = MULTI_FACTOR_STRATEGY_ID
    trend_weight: PositiveDecimal = Decimal("0.30")
    momentum_weight: PositiveDecimal = Decimal("0.25")
    vwap_weight: PositiveDecimal = Decimal("0.20")
    volatility_weight: PositiveDecimal = Decimal("0.25")
    minimum_combined_score: PositiveDecimal = Decimal("0.60")
    momentum_minimum_rsi: NonNegativeDecimal = Decimal("50")
    momentum_maximum_rsi: PositiveDecimal = Decimal("80")
    stop_atr_multiple: PositiveDecimal = Decimal("1")
    expected_move_atr_multiple: PositiveDecimal = Decimal("2")
    maximum_atr_return: PositiveDecimal = Decimal("0.05")

    @model_validator(mode="after")
    def validate_multi_factor(self) -> Self:
        if self.strategy_id != MULTI_FACTOR_STRATEGY_ID:
            raise ValueError("multi-factor configuration has the wrong strategy identity")
        with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
            total = (
                self.trend_weight + self.momentum_weight + self.vwap_weight + self.volatility_weight
            )
        if total != Decimal(1):
            raise ValueError("multi-factor weights must sum exactly to 1")
        if self.minimum_combined_score > 1:
            raise ValueError("multi-factor minimum score must not exceed 1")
        if self.momentum_minimum_rsi >= self.momentum_maximum_rsi:
            raise ValueError("multi-factor RSI bounds must be strictly increasing")
        if self.momentum_maximum_rsi > 100:
            raise ValueError("multi-factor maximum RSI must not exceed 100")
        return self


StrategyConfiguration = Annotated[
    MomentumConfiguration
    | MeanReversionConfiguration
    | BreakoutConfiguration
    | MultiFactorConfiguration,
    Field(discriminator="profile"),
]


def calculate_strategy_configuration_id(
    configuration: StrategyConfiguration,
) -> StrategyConfigurationId:
    return StrategyConfigurationId.parse(sha256_content_id(configuration))


REGISTERED_BASELINE_CONFIGURATIONS: tuple[StrategyConfiguration, ...] = (
    MomentumConfiguration(),
    MeanReversionConfiguration(),
    BreakoutConfiguration(),
    MultiFactorConfiguration(),
)


def baseline_configuration(strategy_id: StrategyId) -> StrategyConfiguration:
    matches = tuple(
        config for config in REGISTERED_BASELINE_CONFIGURATIONS if config.strategy_id == strategy_id
    )
    if len(matches) != 1:
        raise ValueError(f"no unique registered baseline for strategy {strategy_id}")
    return matches[0]
