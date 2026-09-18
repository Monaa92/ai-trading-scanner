"""Immutable causal FX evidence and conversion-policy contracts for Phase 6.2.

Pure and evidence-only. This module defines what an FX observation and an FX
conversion policy *are* and validates their internal consistency; it does not
select among observations, compute a conversion, build balanced ledger legs,
bind into the run manifest, or post any economic effect. No FX rate, quote
convention or staleness threshold has an engine-supplied default: every value
is caller-supplied evidence or an explicit, versioned policy choice.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_trading_scanner.domain import FxConversionPolicyId, FxObservationId
from ai_trading_scanner.domain.content_identity import sha256_content_id_v2
from ai_trading_scanner.simulation.costs import CostRoundingPolicy

_CURRENCY_PATTERN = r"^[A-Z]{3}$"


def _identity_content(
    value: BaseModel | dict[str, object], identity_field: str
) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude={identity_field})
    return {key: item for key, item in value.items() if key != identity_field}


def _normalized_decimal_content(
    value: BaseModel | dict[str, object], identity_field: str, fields: tuple[str, ...]
) -> dict[str, object]:
    content = _identity_content(value, identity_field)
    for field in fields:
        item = content.get(field)
        if item is not None and not isinstance(item, Decimal | float):
            content[field] = Decimal(item)  # type: ignore[arg-type]
    return content


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _reject_float(value: object, label: str) -> object:
    if isinstance(value, float):
        raise ValueError(f"{label} must use Decimal or a decimal string, not float")
    return value


class FxQuoteConvention(StrEnum):
    """Explicit, versioned side/price convention an FX policy or observation may use.

    No convention is an implicit production default; every observation and
    policy must name the one it uses.
    """

    BID = "BID"
    ASK = "ASK"
    MID = "MID"
    DECLARED_REFERENCE = "DECLARED_REFERENCE"


class FxObservationReference(BaseModel):
    """Immutable causal FX evidence.

    Modeled on the accepted `MarketEventReference` causal-availability shape:
    the observation cannot be used before `available_at`, exactly like a
    market bar. The `rate` is supplied evidence from an external provider; it
    is never computed, defaulted or invented by this contract or by any
    engine code that consumes it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fx_observation_id: FxObservationId
    schema_version: Literal["fx-observation-reference-v1"] = "fx-observation-reference-v1"
    base_currency: str = Field(min_length=3, max_length=3, pattern=_CURRENCY_PATTERN)
    quote_currency: str = Field(min_length=3, max_length=3, pattern=_CURRENCY_PATTERN)
    provider: str = Field(min_length=1)
    methodology_version: str = Field(min_length=1)
    quote_convention: FxQuoteConvention
    rate: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    observed_at: datetime
    available_at: datetime
    source_record_id: str | None = None

    @field_validator("rate", mode="before")
    @classmethod
    def reject_float_rate(cls, value: object) -> object:
        return _reject_float(value, "FX rate")

    @field_validator("observed_at", "available_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        if self.base_currency == self.quote_currency:
            raise ValueError("an FX observation requires two distinct currencies")
        if self.available_at < self.observed_at:
            raise ValueError("an FX observation cannot be available before it was observed")
        if self.fx_observation_id != calculate_fx_observation_id(self):
            raise ValueError("FX observation identity does not match content")
        return self


def calculate_fx_observation_id(
    observation: FxObservationReference | dict[str, object],
) -> FxObservationId:
    content = _normalized_decimal_content(observation, "fx_observation_id", ("rate",))
    return FxObservationId.parse(sha256_content_id_v2(content))


class FxConversionPolicyConfiguration(BaseModel):
    """Immutable, versioned FX conversion/valuation policy.

    No default rate, quote convention or staleness threshold is supplied by
    the engine: every field here is an explicit, sourced registration
    decision, mirroring how `SimulationLiquidityConfiguration` carries no
    default participation ceiling. This configuration does not select an
    observation, compute a conversion or bind into any run manifest.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fx_conversion_policy_id: FxConversionPolicyId
    schema_version: Literal["fx-conversion-policy-v1"] = "fx-conversion-policy-v1"
    policy_name: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    base_currency: str = Field(min_length=3, max_length=3, pattern=_CURRENCY_PATTERN)
    trading_currency: str = Field(min_length=3, max_length=3, pattern=_CURRENCY_PATTERN)
    quote_convention: FxQuoteConvention
    maximum_observation_staleness_seconds: Annotated[int, Field(gt=0)]
    rounding_policy: CostRoundingPolicy

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.base_currency == self.trading_currency:
            raise ValueError("an FX conversion policy requires two distinct currencies")
        if self.fx_conversion_policy_id != calculate_fx_conversion_policy_id(self):
            raise ValueError("FX conversion policy identity does not match content")
        return self


def calculate_fx_conversion_policy_id(
    configuration: FxConversionPolicyConfiguration | dict[str, object],
) -> FxConversionPolicyId:
    return FxConversionPolicyId.parse(
        sha256_content_id_v2(_identity_content(configuration, "fx_conversion_policy_id"))
    )
