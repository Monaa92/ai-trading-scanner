"""Immutable indicator configuration and output models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_trading_scanner.domain import DatasetId, IndicatorConfigurationId, InstrumentId
from ai_trading_scanner.domain.content_identity import sha256_content_id
from ai_trading_scanner.market_data import QualityFinding, Timeframe

PositivePeriod = Annotated[int, Field(strict=True, gt=0)]


class IndicatorName(StrEnum):
    EMA = "EMA"
    RSI = "RSI"
    ATR = "ATR"
    SESSION_VWAP = "SESSION_VWAP"


class SmoothingMethod(StrEnum):
    WILDER = "WILDER"


class PriceBasis(StrEnum):
    TYPICAL_PRICE = "TYPICAL_PRICE"


class ResetPolicy(StrEnum):
    SESSION = "SESSION"


class IndicatorReason(StrEnum):
    READY = "READY"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    MISSING_INTERVAL = "MISSING_INTERVAL"
    INCOMPLETE_SESSION_PREFIX = "INCOMPLETE_SESSION_PREFIX"
    ZERO_CUMULATIVE_VOLUME = "ZERO_CUMULATIVE_VOLUME"


class IndicatorUnit(StrEnum):
    PRICE = "PRICE"
    PERCENT = "PERCENT"


class EMAConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    indicator: Literal[IndicatorName.EMA] = IndicatorName.EMA
    implementation_version: Literal["ema-sma-seed-session-v1"] = "ema-sma-seed-session-v1"
    period: PositivePeriod


class RSIConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    indicator: Literal[IndicatorName.RSI] = IndicatorName.RSI
    implementation_version: Literal["rsi-wilder-session-v1"] = "rsi-wilder-session-v1"
    period: PositivePeriod
    smoothing: Literal[SmoothingMethod.WILDER]


class ATRConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    indicator: Literal[IndicatorName.ATR] = IndicatorName.ATR
    implementation_version: Literal["atr-wilder-session-v1"] = "atr-wilder-session-v1"
    period: PositivePeriod
    smoothing: Literal[SmoothingMethod.WILDER]


class VWAPConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    indicator: Literal[IndicatorName.SESSION_VWAP] = IndicatorName.SESSION_VWAP
    implementation_version: Literal["bar-typical-price-vwap-v1"] = "bar-typical-price-vwap-v1"
    price_basis: Literal[PriceBasis.TYPICAL_PRICE]
    reset_policy: Literal[ResetPolicy.SESSION]


IndicatorConfiguration = EMAConfig | RSIConfig | ATRConfig | VWAPConfig


def calculate_indicator_configuration_id(
    configuration: IndicatorConfiguration,
) -> IndicatorConfigurationId:
    return IndicatorConfigurationId.parse(sha256_content_id(configuration))


class IndicatorPoint(BaseModel):
    """One causal value aligned with one completed input bar."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    instrument_id: InstrumentId
    timeframe: Timeframe
    session_id: str
    bar_start_at: datetime
    bar_end_at: datetime
    bar_available_at: datetime
    configuration_id: IndicatorConfigurationId
    value: Decimal | None
    ready: bool
    reason: IndicatorReason

    @model_validator(mode="after")
    def validate_availability(self) -> Self:
        if self.ready and (self.value is None or self.reason is not IndicatorReason.READY):
            raise ValueError("ready indicator point requires a value and READY reason")
        if not self.ready and (self.value is not None or self.reason is IndicatorReason.READY):
            raise ValueError("unavailable indicator point requires null value and non-READY reason")
        return self


class IndicatorSeries(BaseModel):
    """Auditable output for one indicator over one canonical causal slice."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: DatasetId
    input_slice_hash_sha256: str
    as_of: datetime
    latest_available_at: datetime
    configuration: IndicatorConfiguration
    configuration_id: IndicatorConfigurationId
    unit: IndicatorUnit
    points: tuple[IndicatorPoint, ...]
    quality_findings: tuple[QualityFinding, ...]

    @model_validator(mode="after")
    def validate_lineage(self) -> Self:
        expected_id = calculate_indicator_configuration_id(self.configuration)
        if self.configuration_id != expected_id:
            raise ValueError("indicator series configuration identity does not match content")
        expected_unit = (
            IndicatorUnit.PERCENT
            if isinstance(self.configuration, RSIConfig)
            else IndicatorUnit.PRICE
        )
        if self.unit is not expected_unit:
            raise ValueError("indicator series unit does not match configuration")
        if not self.points:
            raise ValueError("indicator series requires at least one point")
        if any(point.configuration_id != self.configuration_id for point in self.points):
            raise ValueError("indicator point configuration identity differs from series")
        if max(point.bar_available_at for point in self.points) != self.latest_available_at:
            raise ValueError("latest_available_at does not match indicator points")
        if self.latest_available_at > self.as_of:
            raise ValueError("indicator series contains future-unavailable points")
        return self
