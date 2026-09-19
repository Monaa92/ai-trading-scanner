"""Immutable causal FX evidence, distinct conversion/valuation policy
contracts, a source-checksum helper, pure causal observation selection
(including quote-side-aware selection), and a pure FX conversion calculation
for Phase 6.2.

Pure and evidence-only. This module defines what an FX observation, an
executable conversion policy and a reporting-only valuation policy *are*,
validates their internal consistency, provides pure selection functions over
an already causally released observation prefix, and calculates the exact
and rounded trading-currency amount for selling a positive base-currency
amount under one causally selected V2 BID observation. A calculation from
this module is not an executed or posted conversion: it moves no capital,
builds no balanced ledger legs, and binds into no run manifest. No FX rate,
quote convention, staleness threshold or currency minor-unit precision has an
engine-supplied default: every value is caller-supplied evidence or an
explicit, versioned policy/calculation choice.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    Inexact,
    InvalidOperation,
    Overflow,
    localcontext,
)
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from ai_trading_scanner.domain import FxConversionPolicyId, FxObservationId, FxValuationPolicyId
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


class FxConversionDirection(StrEnum):
    """Explicit, versioned conversion direction; no default.

    Intentionally incomplete: only the one owner-approved direction is
    listed. Adding a second direction (e.g. selling the trading currency for
    the base currency) requires its own explicit, owner-approved required
    quote-side rule before being added here — it is never inferred from this
    one by symmetry or any other assumption.
    """

    SELL_BASE_FOR_TRADING = "SELL_BASE_FOR_TRADING"
    """Sell the base currency to obtain the trading currency (e.g. sell EUR,
    receive USD). Requires a sourced BID observation."""


_REQUIRED_QUOTE_SIDE_BY_DIRECTION: dict[FxConversionDirection, FxQuoteConvention] = {
    FxConversionDirection.SELL_BASE_FOR_TRADING: FxQuoteConvention.BID,
}


class FxConversionPolicyConfiguration(BaseModel):
    """Immutable, versioned FX conversion/valuation policy.

    No default rate, quote convention or staleness threshold is supplied by
    the engine: every field here is an explicit, sourced registration
    decision, mirroring how `SimulationLiquidityConfiguration` carries no
    default participation ceiling. This configuration does not select an
    observation, compute a conversion or bind into any run manifest.

    `schema_version` `"fx-conversion-policy-v1"` is the original, accepted
    shape: `conversion_direction` must be absent and `quote_convention` is
    unrestricted. `"fx-conversion-policy-v2"` additionally requires
    `conversion_direction` and structurally enforces the one owner-approved
    rule: a `SELL_BASE_FOR_TRADING` policy's `quote_convention` must be
    `BID`. V1 identities are unaffected by V2's existence — the new field is
    excluded from a V1 instance's identity content, so every already-accepted
    V1 policy hashes exactly as before.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fx_conversion_policy_id: FxConversionPolicyId
    schema_version: Literal["fx-conversion-policy-v1", "fx-conversion-policy-v2"] = (
        "fx-conversion-policy-v1"
    )
    policy_name: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    base_currency: str = Field(min_length=3, max_length=3, pattern=_CURRENCY_PATTERN)
    trading_currency: str = Field(min_length=3, max_length=3, pattern=_CURRENCY_PATTERN)
    quote_convention: FxQuoteConvention
    maximum_observation_staleness_seconds: Annotated[int, Field(gt=0)]
    rounding_policy: CostRoundingPolicy
    conversion_direction: FxConversionDirection | None = None

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.base_currency == self.trading_currency:
            raise ValueError("an FX conversion policy requires two distinct currencies")
        is_v2 = self.schema_version == "fx-conversion-policy-v2"
        if is_v2 != (self.conversion_direction is not None):
            raise ValueError(
                "a V2 conversion policy requires conversion_direction and a V1 "
                "conversion policy forbids it"
            )
        if is_v2:
            assert self.conversion_direction is not None
            required_side = _REQUIRED_QUOTE_SIDE_BY_DIRECTION[self.conversion_direction]
            if self.quote_convention is not required_side:
                raise ValueError(
                    f"a {self.conversion_direction} conversion policy requires "
                    f"quote_convention {required_side}, never a different side"
                )
        if self.fx_conversion_policy_id != calculate_fx_conversion_policy_id(self):
            raise ValueError("FX conversion policy identity does not match content")
        return self


def calculate_fx_conversion_policy_id(
    configuration: FxConversionPolicyConfiguration | dict[str, object],
) -> FxConversionPolicyId:
    content = _identity_content(configuration, "fx_conversion_policy_id")
    if content.get("schema_version", "fx-conversion-policy-v1") == "fx-conversion-policy-v1":
        # Preserve all accepted V1 conversion-policy identities after adding
        # the optional V2 conversion_direction field.
        content.pop("conversion_direction", None)
    return FxConversionPolicyId.parse(sha256_content_id_v2(content))


class FxObservationUnavailableReason(StrEnum):
    """Typed reason a causal FX observation selection could not be completed."""

    NO_ELIGIBLE_OBSERVATION = "NO_ELIGIBLE_OBSERVATION"


class FxObservationUnavailable(BaseModel):
    """Pure typed evidence that no released FX observation was eligible at T.

    This is a plain return value from `select_eligible_fx_observation`, not a
    posted, stored or content-identified record. If a later step persists
    this evidence into a replay trace, it should gain a content identity
    then, mirroring every other Phase 6 evidence contract.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: FxObservationUnavailableReason
    evaluated_at: datetime
    fx_conversion_policy_id: FxConversionPolicyId


def select_eligible_fx_observation(
    released_prefix: Sequence[FxObservationReference],
    policy: FxConversionPolicyConfiguration,
    evaluated_at: datetime,
) -> FxObservationReference | FxObservationUnavailable:
    """Pure selection over an already causally released FX observation prefix.

    Callers must supply a prefix already limited to what is causally released
    as of `evaluated_at` (the same trust boundary `order_resolution.py`'s
    candidate filters place on their caller's released view); this function
    additionally enforces `available_at <= evaluated_at` itself rather than
    only trusting that precondition, matching the project's established
    defense-in-depth pattern. It never selects an observation whose
    `available_at` is after `evaluated_at`, regardless of what the caller
    supplied.

    Eligibility requires, for every candidate: the observation's currency
    pair matches the policy's `base_currency`/`trading_currency`; quality is
    exactly `VALIDATED` (`UNVALIDATED` and `SUSPECT` are always ineligible,
    with no override or toggle); `available_at <= evaluated_at`; and
    `evaluated_at - observed_at <= policy.maximum_observation_staleness_seconds`
    — age is measured from `observed_at`, not `available_at`, so an
    observation that was already old when it became available cannot slip
    through by being used the instant it is published.

    Among eligible candidates, the one with the latest `observed_at` wins,
    tie-broken by `(observed_at, available_at, fx_observation_id)`
    descending. When no candidate qualifies, returns typed
    `FxObservationUnavailable` evidence rather than fabricating a rate or
    borrowing a future/stale one.

    Does not check quote convention, compute a conversion, or select a
    bid/ask side; that boundary belongs to a later, separately reviewed step.
    """
    evaluated_at = _aware_utc(evaluated_at)
    staleness_limit = timedelta(seconds=policy.maximum_observation_staleness_seconds)
    candidates = [
        observation
        for observation in released_prefix
        if observation.base_currency == policy.base_currency
        and observation.quote_currency == policy.trading_currency
        and observation.quality_status is FxObservationQualityStatus.VALIDATED
        and observation.available_at <= evaluated_at
        and (evaluated_at - observation.observed_at) <= staleness_limit
    ]
    if not candidates:
        return FxObservationUnavailable(
            reason=FxObservationUnavailableReason.NO_ELIGIBLE_OBSERVATION,
            evaluated_at=evaluated_at,
            fx_conversion_policy_id=policy.fx_conversion_policy_id,
        )
    return max(
        candidates,
        key=lambda observation: (
            observation.observed_at,
            observation.available_at,
            str(observation.fx_observation_id),
        ),
    )


def calculate_fx_source_checksum(
    *,
    base_currency: str,
    quote_currency: str,
    provider: str,
    quote_convention: FxQuoteConvention,
    rate: Decimal | str,
    observed_at: datetime,
) -> str:
    """Pure, independently reproducible checksum of a provider's reported FX fact.

    Hashes exactly six logical fields using this project's existing V2
    canonicalization and SHA-256 content-identity helpers (unchanged, the
    same ones every other Phase 6 identity uses): `base_currency`,
    `quote_currency`, `provider`, `quote_convention`, `rate` and
    `observed_at`. Deliberately excludes `available_at` and any
    ingestion/quality metadata, which describe our handling of the fact, not
    the fact itself.

    This checksum represents the **normalized** provider fact, not the
    provider's original transport bytes: the Decimal representation is
    scale-invariant (`"1.08"` and `"1.0800"` produce the same checksum,
    exactly like every other Phase 6 V2 content identity), and the timestamp
    uses the shared canonical UTC form. It cannot prove the provider's exact
    reported precision or wire encoding, only that the same normalized fact
    was reported. Callers are responsible for storing the resulting value in
    `FxObservationReference.source_checksum` if desired; this function does
    not validate, select among, or bind to any `FxObservationReference`.
    """
    if isinstance(rate, float):
        raise ValueError("rate must use Decimal or a decimal string, not float")
    decimal_rate = rate if isinstance(rate, Decimal) else Decimal(rate)
    if not decimal_rate.is_finite():
        raise ValueError("rate must be a finite Decimal value")
    content: dict[str, object] = {
        "base_currency": base_currency,
        "quote_currency": quote_currency,
        "provider": provider,
        "quote_convention": quote_convention,
        "rate": decimal_rate,
        "observed_at": _aware_utc(observed_at),
    }
    return sha256_content_id_v2(content)


class FxValuationPolicyConfiguration(BaseModel):
    """Immutable, versioned reporting-only FX valuation policy.

    Distinct from `FxConversionPolicyConfiguration`: this policy marks
    equity/positions for reporting only. It never moves capital and never
    incurs a conversion cost — there is no capital-movement or cost field on
    this type, and none exists anywhere in this module to invoke. Its
    `quote_convention` is restricted to `MID` or `DECLARED_REFERENCE`; `BID`
    and `ASK` (transactional sides) are never valid here, since no trade
    occurs. No default rate, quote convention or staleness threshold is
    supplied by the engine, mirroring `FxConversionPolicyConfiguration`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fx_valuation_policy_id: FxValuationPolicyId
    schema_version: Literal["fx-valuation-policy-v1"] = "fx-valuation-policy-v1"
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
            raise ValueError("an FX valuation policy requires two distinct currencies")
        if self.quote_convention not in (
            FxQuoteConvention.MID,
            FxQuoteConvention.DECLARED_REFERENCE,
        ):
            raise ValueError(
                "an FX valuation policy must use MID or DECLARED_REFERENCE, never a "
                "transactional BID/ASK side"
            )
        if self.fx_valuation_policy_id != calculate_fx_valuation_policy_id(self):
            raise ValueError("FX valuation policy identity does not match content")
        return self


def calculate_fx_valuation_policy_id(
    configuration: FxValuationPolicyConfiguration | dict[str, object],
) -> FxValuationPolicyId:
    return FxValuationPolicyId.parse(
        sha256_content_id_v2(_identity_content(configuration, "fx_valuation_policy_id"))
    )


class FxQuoteUnavailableReason(StrEnum):
    """Typed reason a quote-side-aware FX observation selection could not be completed."""

    NO_ELIGIBLE_OBSERVATION = "NO_ELIGIBLE_OBSERVATION"
    REQUIRED_QUOTE_SIDE_UNAVAILABLE = "REQUIRED_QUOTE_SIDE_UNAVAILABLE"


class FxConversionQuoteUnavailable(BaseModel):
    """Pure typed evidence that no observation satisfied a conversion policy's
    required quote side at T. A plain return value, not content-identified;
    see `FxObservationUnavailable` for the same rationale."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: FxQuoteUnavailableReason
    evaluated_at: datetime
    fx_conversion_policy_id: FxConversionPolicyId


class FxValuationQuoteUnavailable(BaseModel):
    """Pure typed evidence that no observation satisfied a valuation policy's
    required quote side at T. Reporting-only valuation must surface this as
    explicitly incomplete reporting rather than inventing a value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: FxQuoteUnavailableReason
    evaluated_at: datetime
    fx_valuation_policy_id: FxValuationPolicyId


def _select_by_quote_side(
    released_prefix: Sequence[FxObservationReference],
    *,
    base_currency: str,
    quote_currency: str,
    maximum_staleness_seconds: int,
    required_quote_convention: FxQuoteConvention,
    evaluated_at: datetime,
) -> tuple[FxObservationReference | None, FxQuoteUnavailableReason | None]:
    """Private helper shared by the conversion/valuation selection functions.

    Reuses the same causal-eligibility criteria as `select_eligible_fx_observation`
    (currency pair, VALIDATED-only quality, `available_at <= evaluated_at`,
    `observed_at`-based staleness, freshest-wins with the same tie-break),
    extended with a required `quote_convention` match. Distinguishes "no
    causally eligible observation at all" from "eligible observations exist
    but none match the required quote side" so callers get an accurate
    reason rather than one generic failure.
    """
    staleness_limit = timedelta(seconds=maximum_staleness_seconds)
    causally_eligible = [
        observation
        for observation in released_prefix
        if observation.base_currency == base_currency
        and observation.quote_currency == quote_currency
        and observation.quality_status is FxObservationQualityStatus.VALIDATED
        and observation.available_at <= evaluated_at
        and (evaluated_at - observation.observed_at) <= staleness_limit
    ]
    if not causally_eligible:
        return None, FxQuoteUnavailableReason.NO_ELIGIBLE_OBSERVATION
    quote_matched = [
        observation
        for observation in causally_eligible
        if observation.quote_convention is required_quote_convention
    ]
    if not quote_matched:
        return None, FxQuoteUnavailableReason.REQUIRED_QUOTE_SIDE_UNAVAILABLE
    selected = max(
        quote_matched,
        key=lambda observation: (
            observation.observed_at,
            observation.available_at,
            str(observation.fx_observation_id),
        ),
    )
    return selected, None


class FxConversionPolicyUnsupportedError(ValueError):
    """Raised when a conversion-selection function receives a policy that is
    not `fx-conversion-policy-v2` with the one approved `conversion_direction`.

    This is a caller/configuration error — the policy itself is unusable for
    an executable conversion — not a causal data-availability outcome. It is
    always raised, never returned as `FxConversionQuoteUnavailable` evidence,
    so an invalid policy can never be mistaken for legitimately missing or
    stale FX data.
    """


def select_eligible_fx_observation_for_conversion(
    released_prefix: Sequence[FxObservationReference],
    policy: FxConversionPolicyConfiguration,
    evaluated_at: datetime,
) -> FxObservationReference | FxConversionQuoteUnavailable:
    """Pure quote-side-aware selection for an executable currency conversion.

    Requires `policy.schema_version == "fx-conversion-policy-v2"` with
    `conversion_direction == SELL_BASE_FOR_TRADING` (the one owner-approved
    direction) — this is what structurally guarantees `quote_convention` is
    the required transactional side (`BID`). A `"fx-conversion-policy-v1"`
    policy, even one whose `quote_convention` happens to already be `BID`,
    is rejected: V1 carries no structural guarantee, so accepting it would
    let a caller bypass the enforced rule by supplying an unenforced,
    differently-configured V1 instance. Raises
    `FxConversionPolicyUnsupportedError` immediately for any policy that
    doesn't satisfy this, before any observation is examined.

    Given a qualifying policy, applies the same causal-eligibility rules as
    `select_eligible_fx_observation`, plus a required exact match on
    `policy.quote_convention`. Never substitutes a different side. Returns
    typed `FxConversionQuoteUnavailable` evidence, distinguishing
    no-eligible-observation from quote-side-specifically-unavailable, rather
    than fabricating or borrowing a rate. Computes no conversion, moves no
    capital, and posts nothing.
    """
    if (
        policy.schema_version != "fx-conversion-policy-v2"
        or policy.conversion_direction is not FxConversionDirection.SELL_BASE_FOR_TRADING
    ):
        raise FxConversionPolicyUnsupportedError(
            "select_eligible_fx_observation_for_conversion requires a "
            "'fx-conversion-policy-v2' policy with conversion_direction "
            "SELL_BASE_FOR_TRADING; got schema_version="
            f"{policy.schema_version!r}, conversion_direction="
            f"{policy.conversion_direction!r}"
        )
    evaluated_at = _aware_utc(evaluated_at)
    selected, reason = _select_by_quote_side(
        released_prefix,
        base_currency=policy.base_currency,
        quote_currency=policy.trading_currency,
        maximum_staleness_seconds=policy.maximum_observation_staleness_seconds,
        required_quote_convention=policy.quote_convention,
        evaluated_at=evaluated_at,
    )
    if selected is not None:
        return selected
    assert reason is not None
    return FxConversionQuoteUnavailable(
        reason=reason,
        evaluated_at=evaluated_at,
        fx_conversion_policy_id=policy.fx_conversion_policy_id,
    )


def select_eligible_fx_observation_for_valuation(
    released_prefix: Sequence[FxObservationReference],
    policy: FxValuationPolicyConfiguration,
    evaluated_at: datetime,
) -> FxObservationReference | FxValuationQuoteUnavailable:
    """Pure quote-side-aware selection for reporting-only FX valuation.

    Same causal-eligibility rules as `select_eligible_fx_observation`, plus a
    required exact match on `policy.quote_convention` (always `MID` or
    `DECLARED_REFERENCE` for a valuation policy — enforced by
    `FxValuationPolicyConfiguration` itself). Never substitutes a different
    side. Returns typed `FxValuationQuoteUnavailable` evidence — the caller
    must treat this as explicitly incomplete reporting, never inventing a
    value. Moves no capital and incurs no cost.
    """
    evaluated_at = _aware_utc(evaluated_at)
    selected, reason = _select_by_quote_side(
        released_prefix,
        base_currency=policy.base_currency,
        quote_currency=policy.trading_currency,
        maximum_staleness_seconds=policy.maximum_observation_staleness_seconds,
        required_quote_convention=policy.quote_convention,
        evaluated_at=evaluated_at,
    )
    if selected is not None:
        return selected
    assert reason is not None
    return FxValuationQuoteUnavailable(
        reason=reason,
        evaluated_at=evaluated_at,
        fx_valuation_policy_id=policy.fx_valuation_policy_id,
    )


class FxConversionInputError(ValueError):
    """Raised for an invalid input to `calculate_fx_conversion` itself.

    This is a caller/configuration error — a malformed request — never a
    causal data-availability outcome, mirroring the same distinction
    `FxConversionPolicyUnsupportedError` already draws for an unsupported
    policy. Covers a non-Decimal or float `base_amount`, a non-finite
    (including NaN/Infinity) or non-positive `base_amount`, a
    `trading_currency_minor_unit_digits` that is not a genuine, non-negative
    `int` (explicitly including `bool`, which Python and Pydantic's default
    lax `int` validation would otherwise silently accept as 0/1), a
    `trading_currency_minor_unit_digits` too large to quantize against, a
    `rounding_policy` this calculation does not yet know how to apply, and a
    `base_amount`/`rate` multiplication that cannot be represented exactly at
    this project's approved 34-digit Decimal precision (see
    `_exact_multiply`). It does not, and cannot, cover an invalid or
    non-finite observation rate or a currency-pair mismatch:
    `FxObservationReference.rate` is already validated
    `gt=0, allow_inf_nan=False` at construction, and every observation this
    function can select already has its currency pair matched to the policy
    by `select_eligible_fx_observation_for_conversion` itself.
    """


_EXACT_ARITHMETIC_CONTEXT = Context(
    prec=34,
    rounding=ROUND_HALF_EVEN,
    traps=[Inexact, InvalidOperation, DivisionByZero, Overflow],
)


def _exact_multiply(base_amount: Decimal, rate: Decimal) -> Decimal:
    """Multiply `base_amount * rate` at this project's approved 34-digit
    `ROUND_HALF_EVEN` Decimal precision, failing closed instead of silently
    rounding.

    Decimal arithmetic rounds *every* operation to fit the ambient context's
    precision, not just an explicit `.quantize()` call: a plain
    `Context(prec=34, ...)` multiplication silently discards significant
    digits whenever the true product needs more than 34 of them, with no
    error and no visible indication anything was lost. That would make a
    value labeled `exact_trading_amount` not actually exact, violating the
    owner-approved no-intermediate-monetary-rounding rule.

    Trapping the `Inexact` signal turns that silent truncation into a raised
    `FxConversionInputError` instead. This does not widen the shared 34-digit
    precision/rounding policy used everywhere else in this project
    (`calculate_fill_costs`, `portfolio.py`, etc.) — the policy is unchanged;
    this only refuses to mislabel a rounded product as exact.
    """
    with localcontext(_EXACT_ARITHMETIC_CONTEXT):
        try:
            return base_amount * rate
        except Inexact as exc:
            raise FxConversionInputError(
                "base_amount * rate cannot be represented exactly at this "
                "project's approved 34-digit Decimal precision; refusing to "
                "return a silently rounded value as exact_trading_amount"
            ) from exc


def _validate_minor_unit_digits(value: object) -> int:
    """Fail closed unless `value` is a genuine, non-negative `int`.

    `bool` is a subclass of `int` in Python — and Pydantic's default lax
    `int` field validation accepts it too — so it must be rejected
    explicitly, never silently treated as a precision of 0 or 1. No other
    non-`int` type (float, str, `None`, ...) is accepted either: this
    project never silently coerces or clamps a caller-supplied precision.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise FxConversionInputError(
            f"trading_currency_minor_unit_digits must be a genuine int, not {type(value).__name__}"
        )
    if value < 0:
        raise FxConversionInputError("trading_currency_minor_unit_digits must be >= 0")
    return value


class FxConversionCalculation(BaseModel):
    """Pure calculated result of selling a positive `base_amount` of
    `base_currency` for `trading_currency`, under one causally selected V2
    BID `FxObservationReference`.

    This is a calculation, not an execution or a posting: it moves no
    capital, mutates no balance, builds no balanced ledger leg, and binds
    into no run manifest or broker order. It is not itself
    content-identified, mirroring `FxConversionQuoteUnavailable` and
    `FxObservationUnavailable` — a plain, auditable return value that
    references existing identities (`fx_conversion_policy_id`,
    `fx_observation_id`) rather than minting a new identity domain.

    `exact_trading_amount` is `base_amount * rate`, computed once via
    `_exact_multiply` at this project's approved 34-digit `ROUND_HALF_EVEN`
    Decimal precision, with no intermediate rounding — constructing this
    model with an `exact_trading_amount` that does not actually equal that
    exact product (including one that was itself silently rounded to fit 34
    digits) fails closed, since `validate_calculation` recomputes it through
    the same `Inexact`-trapping `_exact_multiply` helper `calculate_fx_conversion`
    uses, rather than through a separate context that could reproduce the same
    precision loss and wrongly validate it. `rounded_trading_amount` is the
    one, separate, final-boundary quantization of that exact amount to
    `trading_currency_minor_unit_digits` decimal places using
    `rounding_policy`. The two fields are never conflated: `exact_*` is the
    unrounded calculation, `rounded_*` is a display/posting-boundary amount
    only, and neither implies any capital has moved.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["fx-conversion-calculation-v1"] = "fx-conversion-calculation-v1"
    fx_conversion_policy_id: FxConversionPolicyId
    fx_observation_id: FxObservationId
    base_currency: str = Field(min_length=3, max_length=3, pattern=_CURRENCY_PATTERN)
    trading_currency: str = Field(min_length=3, max_length=3, pattern=_CURRENCY_PATTERN)
    base_amount: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    rate: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    evaluated_at: datetime
    exact_trading_amount: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    trading_currency_minor_unit_digits: Annotated[int, Field(ge=0)]
    rounding_policy: CostRoundingPolicy
    rounded_trading_amount: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]

    @field_validator(
        "base_amount", "rate", "exact_trading_amount", "rounded_trading_amount", mode="before"
    )
    @classmethod
    def reject_float_amounts(cls, value: object, info: ValidationInfo) -> object:
        return _reject_float(value, str(info.field_name))

    @field_validator("trading_currency_minor_unit_digits", mode="before")
    @classmethod
    def reject_non_genuine_int_minor_unit_digits(cls, value: object) -> object:
        return _validate_minor_unit_digits(value)

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_calculation(self) -> Self:
        if self.base_currency == self.trading_currency:
            raise ValueError("an FX conversion calculation requires two distinct currencies")
        expected_exact = _exact_multiply(self.base_amount, self.rate)
        if self.exact_trading_amount != expected_exact:
            raise ValueError("exact_trading_amount must equal base_amount * rate, unrounded")
        expected_rounded = _quantize_to_minor_unit(
            self.exact_trading_amount, self.trading_currency_minor_unit_digits, self.rounding_policy
        )
        if self.rounded_trading_amount != expected_rounded:
            raise ValueError(
                "rounded_trading_amount must equal exact_trading_amount quantized to "
                "trading_currency_minor_unit_digits using rounding_policy"
            )
        return self


def _quantize_to_minor_unit(
    exact_amount: Decimal, minor_unit_digits: int, rounding_policy: CostRoundingPolicy
) -> Decimal:
    if rounding_policy is not CostRoundingPolicy.ROUND_HALF_EVEN_V1:
        raise FxConversionInputError(
            f"calculate_fx_conversion does not support rounding_policy {rounding_policy!r}"
        )
    quantum = Decimal(1).scaleb(-minor_unit_digits)
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        try:
            return exact_amount.quantize(quantum, rounding=ROUND_HALF_EVEN)
        except InvalidOperation as exc:
            raise FxConversionInputError(
                f"exact_trading_amount cannot be quantized to {minor_unit_digits} minor-unit digits"
            ) from exc


def calculate_fx_conversion(
    released_prefix: Sequence[FxObservationReference],
    policy: FxConversionPolicyConfiguration,
    base_amount: Decimal,
    trading_currency_minor_unit_digits: int,
    evaluated_at: datetime,
) -> FxConversionCalculation | FxConversionQuoteUnavailable:
    """Pure calculation of selling `base_amount` of the base currency for the
    trading currency, under one causally selected, quote-side-matched V2 BID
    observation. Computes no capital movement, balanced ledger leg, fee, or
    manifest binding — an executable or posted conversion is a separate,
    not-yet-implemented step.

    Selects the observation itself, by delegating entirely to
    `select_eligible_fx_observation_for_conversion` over the supplied
    `released_prefix`/`policy`/`evaluated_at` — it never accepts an
    already-selected `FxObservationReference` from the caller. This is what
    makes the V2/BID/causal-selection boundary impossible to bypass: there is
    no code path here that can use an observation this function did not
    itself select through that existing, already-enforced boundary. A `V1`
    policy, an unsupported direction, or a non-`SELL_BASE_FOR_TRADING`
    direction is rejected by that selector's own
    `FxConversionPolicyUnsupportedError`, propagated unchanged. When no
    causally eligible, quote-side-matched observation exists, the selector's
    typed `FxConversionQuoteUnavailable` evidence is returned directly and no
    calculation is attempted.

    Raises `FxConversionInputError` for an invalid `base_amount` (float,
    non-Decimal, non-finite/NaN/Infinity, zero, or negative), a
    `trading_currency_minor_unit_digits` that is not a genuine, non-negative
    `int` (a `bool` is explicitly rejected, never silently treated as 0/1) or
    that is too large to quantize against, a `rounding_policy` this
    calculation does not support, or a `base_amount`/`rate` multiplication
    that cannot be represented exactly at this project's approved 34-digit
    Decimal precision (see `_exact_multiply`) — this function never returns a
    silently rounded product under the name `exact_trading_amount`.
    `trading_currency_minor_unit_digits` has no default: callers must state
    explicitly how many decimal places the trading currency uses (never
    assumed to be 2, and never silently clamped).

    `exact_trading_amount = base_amount * rate` is computed once, unrounded,
    via `_exact_multiply`. `rounded_trading_amount` is a single, separate
    quantization of that exact amount to `trading_currency_minor_unit_digits`
    decimal places — the one documented final rounding boundary. Both are
    returned, never conflated.
    """
    if isinstance(base_amount, float):
        raise FxConversionInputError("base_amount must use Decimal, not float")
    if not isinstance(base_amount, Decimal):
        raise FxConversionInputError("base_amount must be a Decimal value")
    if not base_amount.is_finite() or base_amount <= 0:
        raise FxConversionInputError("base_amount must be a finite, positive Decimal value")
    trading_currency_minor_unit_digits = _validate_minor_unit_digits(
        trading_currency_minor_unit_digits
    )

    selection = select_eligible_fx_observation_for_conversion(released_prefix, policy, evaluated_at)
    if isinstance(selection, FxConversionQuoteUnavailable):
        return selection
    observation = selection

    normalized_evaluated_at = _aware_utc(evaluated_at)
    exact_trading_amount = _exact_multiply(base_amount, observation.rate)
    rounded_trading_amount = _quantize_to_minor_unit(
        exact_trading_amount, trading_currency_minor_unit_digits, policy.rounding_policy
    )

    return FxConversionCalculation(
        fx_conversion_policy_id=policy.fx_conversion_policy_id,
        fx_observation_id=observation.fx_observation_id,
        base_currency=policy.base_currency,
        trading_currency=policy.trading_currency,
        base_amount=base_amount,
        rate=observation.rate,
        evaluated_at=normalized_evaluated_at,
        exact_trading_amount=exact_trading_amount,
        trading_currency_minor_unit_digits=trading_currency_minor_unit_digits,
        rounding_policy=policy.rounding_policy,
        rounded_trading_amount=rounded_trading_amount,
    )
