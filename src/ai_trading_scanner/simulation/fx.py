"""Immutable causal FX evidence and conversion-policy contracts for Phase 6.2.

Pure and evidence-only. This module defines what an FX observation and an FX
conversion policy *are* and validates their internal consistency; it does not
select among observations, compute a conversion, build balanced ledger legs,
bind into the run manifest, or post any economic effect. No FX rate, quote
convention or staleness threshold has an engine-supplied default: every value
is caller-supplied evidence or an explicit, versioned policy choice.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from ai_trading_scanner.domain import FxConversionPolicyId, FxObservationId
from ai_trading_scanner.domain.content_identity import sha256_content_id_v2
from ai_trading_scanner.simulation.costs import CostRoundingPolicy

_CURRENCY_PATTERN = r"^[A-Z]{3}$"

# Reuses this project's own content-identity format (`sha256:` + 64 lowercase
# hex characters, as produced by ai_trading_scanner.domain.content_identity)
# rather than inventing a new checksum convention. A checksum is presumed to
# identify the exact upstream FX record byte-for-byte; any other algorithm or
# encoding requires a new, explicitly named field and schema version.
_CHECKSUM_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def _identity_content(
    value: BaseModel | dict[str, object], identity_field: str
) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude={identity_field})
    return {key: item for key, item in value.items() if key != identity_field}


def _is_meaningful_text(value: str | None) -> bool:
    """True only for a non-`None` string with at least one non-whitespace character."""
    return value is not None and value.strip() != ""


def _normalized_decimal_content(
    value: BaseModel | dict[str, object], identity_field: str, fields: tuple[str, ...]
) -> dict[str, object]:
    """Return identity content with the named fields coerced to finite Decimal.

    This is the public identity boundary for Decimal-typed fields: it must
    reject binary floats, non-finite values and malformed input exactly like
    the model's own field validators, even when called directly on a raw
    dict rather than through a validated model instance.
    """
    content = _identity_content(value, identity_field)
    for field in fields:
        item = content.get(field)
        if item is None:
            continue
        if isinstance(item, float):
            raise ValueError(f"{field!r} must use Decimal or a decimal string, not float")
        if isinstance(item, Decimal):
            decimal_item = item
        else:
            try:
                decimal_item = Decimal(item)  # type: ignore[arg-type]
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValueError(f"{field!r} must be a valid Decimal value") from exc
        if not decimal_item.is_finite():
            raise ValueError(f"{field!r} must be a finite Decimal value")
        content[field] = decimal_item
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


class FxObservationQualityStatus(StrEnum):
    """Explicit quality classification for one FX observation; no default.

    This names the states an observation's quality review can be in. It does
    not itself assess or assign a production quality outcome; every
    observation must state which status applies to it.
    """

    UNVALIDATED = "UNVALIDATED"
    VALIDATED = "VALIDATED"
    SUSPECT = "SUSPECT"


class FxObservationReference(BaseModel):
    """Immutable causal FX evidence.

    Modeled on the accepted `MarketEventReference` causal-availability shape:
    the observation cannot be used before `available_at`, exactly like a
    market bar. The `rate` is supplied evidence from an external provider; it
    is never computed, defaulted or invented by this contract or by any
    engine code that consumes it. Provenance and quality fields make the
    evidence auditable: which source dataset and version it came from, the
    exact record or checksum that identifies it, how it was ingested, and its
    explicit quality classification. All of them are bound into
    `fx_observation_id`, so changing any one changes the observation's
    identity.

    `provider`, `methodology_version`, `source_dataset_id`,
    `source_dataset_version` and `ingestion_provenance` must be nonblank
    after stripping whitespace; a string that is empty or contains only
    whitespace is rejected exactly like a missing value. When supplied,
    `source_checksum` must match `sha256:` followed by 64 lowercase hex
    characters — this project's own content-identity format — and is
    rejected as malformed otherwise, whether or not `source_record_id` is
    also present. `source_record_id` remains optional, but when supplied it
    must also be nonblank — an empty or whitespace-only value is rejected
    even when a valid `source_checksum` is also present. At least one of
    `source_record_id`/`source_checksum` must still be present and
    meaningful.
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
    source_dataset_id: str = Field(min_length=1)
    source_dataset_version: str = Field(min_length=1)
    source_record_id: str | None = None
    source_checksum: str | None = None
    ingestion_provenance: str = Field(min_length=1)
    quality_status: FxObservationQualityStatus

    @field_validator("rate", mode="before")
    @classmethod
    def reject_float_rate(cls, value: object) -> object:
        return _reject_float(value, "FX rate")

    @field_validator("observed_at", "available_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @field_validator(
        "provider",
        "methodology_version",
        "source_dataset_id",
        "source_dataset_version",
        "ingestion_provenance",
    )
    @classmethod
    def reject_blank_provenance_text(cls, value: str, info: ValidationInfo) -> str:
        if not _is_meaningful_text(value):
            raise ValueError(f"{info.field_name} must be nonblank, not empty or whitespace-only")
        return value

    @field_validator("source_checksum")
    @classmethod
    def validate_checksum_format(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not _is_meaningful_text(value):
            raise ValueError("source_checksum must be nonblank when supplied")
        if not _CHECKSUM_PATTERN.fullmatch(value):
            raise ValueError(
                "source_checksum must match 'sha256:' followed by 64 lowercase hex characters"
            )
        return value

    @field_validator("source_record_id")
    @classmethod
    def validate_record_id_nonblank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not _is_meaningful_text(value):
            raise ValueError("source_record_id must be nonblank when supplied")
        return value

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        if self.base_currency == self.quote_currency:
            raise ValueError("an FX observation requires two distinct currencies")
        if self.available_at < self.observed_at:
            raise ValueError("an FX observation cannot be available before it was observed")
        if not (
            _is_meaningful_text(self.source_record_id) or _is_meaningful_text(self.source_checksum)
        ):
            raise ValueError(
                "an FX observation requires a nonblank source_record_id or source_checksum"
            )
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
