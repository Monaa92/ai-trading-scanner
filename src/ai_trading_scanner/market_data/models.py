"""Immutable canonical market-data records and provenance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_trading_scanner.domain import InstrumentId


class Timeframe(StrEnum):
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_60 = "60m"

    @property
    def duration(self) -> timedelta:
        return {
            Timeframe.MINUTE_1: timedelta(minutes=1),
            Timeframe.MINUTE_5: timedelta(minutes=5),
            Timeframe.MINUTE_15: timedelta(minutes=15),
            Timeframe.MINUTE_60: timedelta(minutes=60),
        }[self]


class AssetClass(StrEnum):
    EQUITY = "EQUITY"
    ETF = "ETF"


class AvailabilityMode(StrEnum):
    ACTUAL = "ACTUAL"
    MODELED = "MODELED"


class AdjustmentMethod(StrEnum):
    RAW = "RAW"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    SPLIT_AND_DIVIDEND_ADJUSTED = "SPLIT_AND_DIVIDEND_ADJUSTED"
    PROVIDER_DEFINED = "PROVIDER_DEFINED"


class QualityStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


class Instrument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    instrument_id: InstrumentId
    symbol: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9.-]+$")
    exchange: str = Field(default="XNYS", min_length=1, max_length=16)
    asset_class: AssetClass
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")


class HistoricalBar(BaseModel):
    """Canonical UTC OHLCV bar covering the half-open interval [start_at, end_at)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    instrument_id: InstrumentId
    session_id: str = Field(min_length=1)
    timeframe: Timeframe
    start_at: datetime
    end_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    source_record_id: str | None = None
    received_at: datetime | None = None
    available_at: datetime
    ingested_at: datetime
    availability_mode: AvailabilityMode

    @field_validator("start_at", "end_at", "received_at", "available_at", "ingested_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)

    @field_validator("open", "high", "low", "close", "volume", mode="before")
    @classmethod
    def reject_float_numbers(cls, value: Any) -> Any:
        if isinstance(value, float):
            raise ValueError("financial values must use decimal strings or Decimal, not float")
        return value

    @model_validator(mode="after")
    def validate_bar(self) -> Self:
        prices = (self.open, self.high, self.low, self.close)
        if any(not price.is_finite() or price <= 0 for price in prices):
            raise ValueError("OHLC prices must be finite and positive")
        if not self.volume.is_finite() or self.volume < 0:
            raise ValueError("volume must be finite and nonnegative")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("OHLC values are inconsistent")
        if self.low > self.high:
            raise ValueError("low cannot exceed high")
        if self.end_at - self.start_at != self.timeframe.duration:
            raise ValueError("bar interval does not match timeframe")
        if self.available_at < self.end_at:
            raise ValueError("bar cannot be available before its interval ends")
        if self.ingested_at < self.available_at:
            raise ValueError("ingested_at cannot precede available_at")
        if self.received_at is not None and self.available_at < self.received_at:
            raise ValueError("available_at cannot precede received_at")
        if self.availability_mode is AvailabilityMode.ACTUAL and self.received_at is None:
            raise ValueError("ACTUAL availability requires received_at")
        return self

    @property
    def event_at(self) -> datetime:
        return self.end_at


class MissingInterval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    start_at: datetime
    end_at: datetime
    reason: str | None = None

    @field_validator("start_at", "end_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("missing interval end must follow start")
        return self


class DataProvenance(BaseModel):
    """Provider and normalization facts required to audit a dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(min_length=1)
    source_dataset_id: str | None = None
    source_dataset_version: str | None = None
    universe_reference: str | None = None
    timeframe: Timeframe
    source_timezone: str
    requested_start_at: datetime | None = None
    requested_end_at: datetime | None = None
    covered_start_at: datetime | None = None
    covered_end_at: datetime | None = None
    ingested_at: datetime
    adjustment_method: AdjustmentMethod
    adjustment_details: str | None = None
    schema_version: str = "market-data-v1"
    availability_mode: AvailabilityMode
    modeled_publication_delay_seconds: Annotated[int | None, Field(ge=0)] = None
    calendar_name: str = "XNYS"
    calendar_version: str
    normalization_version: str
    quality_status: QualityStatus = QualityStatus.UNKNOWN
    missing_intervals: tuple[MissingInterval, ...] = ()
    source_checksum_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator(
        "requested_start_at",
        "requested_end_at",
        "covered_start_at",
        "covered_end_at",
        "ingested_at",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)

    @field_validator("source_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("source_timezone must be a valid IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        pairs = (
            (self.requested_start_at, self.requested_end_at, "requested"),
            (self.covered_start_at, self.covered_end_at, "covered"),
        )
        for start, end, label in pairs:
            if (start is None) != (end is None):
                raise ValueError(f"{label} coverage requires both start and end")
            if start is not None and end is not None and end <= start:
                raise ValueError(f"{label} coverage end must follow start")
        if self.availability_mode is AvailabilityMode.MODELED:
            if self.modeled_publication_delay_seconds is None:
                raise ValueError("MODELED availability requires an explicit publication delay")
        elif self.modeled_publication_delay_seconds is not None:
            raise ValueError("ACTUAL availability cannot declare a modeled publication delay")
        if (
            self.adjustment_method is AdjustmentMethod.PROVIDER_DEFINED
            and not self.adjustment_details
        ):
            raise ValueError("provider-defined adjustments require adjustment_details")
        return self
