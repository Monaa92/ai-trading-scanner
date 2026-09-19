"""Pure, immutable FX conversion reservation, authorization and posting
evidence contracts for Phase 6.2.

Pure and evidence-only, exactly like `ai_trading_scanner.simulation.fx`:
this module defines what a proposed FX conversion reservation, its
authorization, and its posting evidence *are*, and validates their internal
and cross-record consistency. It does not implement a capital coordinator,
does not transition any reservation, does not mutate any cash ledger or
portfolio balance, and does not claim that any actual cash movement
occurred. Constructing any type in this module has no side effect and moves
no capital. A future, separately authorized step would be required to give
any of this evidence operational meaning against real ledger state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, InvalidOperation, localcontext
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_trading_scanner.domain import (
    AccountId,
    AgentId,
    AllocationId,
    ExecutionDimensions,
    ExecutionEnvironment,
    FxConversionAuthorizationId,
    FxConversionPostingEvidenceId,
    FxConversionRequestId,
    FxConversionReservationId,
)
from ai_trading_scanner.domain.content_identity import sha256_content_id_v2
from ai_trading_scanner.risk.models import ReservationState
from ai_trading_scanner.simulation.fx import (
    FxConversionCalculation,
    FxConversionInputError,
    validate_minor_unit_digits,
)

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
    """Return identity content with the named top-level fields coerced to
    finite Decimal, exactly like `simulation.fx`'s own helper of the same
    shape. Only applies to fields owned directly by `value` -- an embedded
    sub-model's own Decimal fields are already normalized by that sub-model
    having been validated before it was embedded (see each contract's own
    docstring for the required construction order)."""
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


def _base_amount_conforms_to_minor_unit_digits(
    base_amount: Decimal, minor_unit_digits: int
) -> bool:
    """True only if quantizing `base_amount` to `minor_unit_digits` decimal
    places leaves it mathematically unchanged -- i.e. it already carries no
    more precision than the currency's own registered minor units allow.
    Never rounds or mutates `base_amount`; this is a pure predicate."""
    quantum = Decimal(1).scaleb(-minor_unit_digits)
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        try:
            return base_amount.quantize(quantum, rounding=ROUND_HALF_EVEN) == base_amount
        except InvalidOperation:
            return False


class FxConversionRequest(BaseModel):
    """The dedicated, content-identified anchor of one FX conversion
    request, independent of any `TradeProposalId`.

    A `TradeProposalId` anchors a full strategy/risk-sized trade intent; an
    FX conversion carries no such upstream proposal, sizing, or instrument,
    so reusing `TradeProposalId` would force an unrelated identity domain
    onto a concept it was never designed for. This is a minimal, standalone
    identity, content-derived from exactly what makes one conversion request
    unique: who is requesting it, what currency pair and amount, and when.
    Two identical requests (same owner, pair, amount, and instant) collapse
    to the same id -- natural idempotency for an exact resubmission. Any
    difference in owner, pair, amount, or `requested_at` is a genuinely
    different request with its own identity.

    Pure evidence of intent only: it reserves nothing, authorizes nothing,
    and moves no capital.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fx_conversion_request_id: FxConversionRequestId
    schema_version: Literal["fx-conversion-request-v1"] = "fx-conversion-request-v1"
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    base_currency: str = Field(min_length=3, max_length=3, pattern=_CURRENCY_PATTERN)
    trading_currency: str = Field(min_length=3, max_length=3, pattern=_CURRENCY_PATTERN)
    requested_amount: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    requested_at: datetime

    @field_validator("requested_amount", mode="before")
    @classmethod
    def reject_float_requested_amount(cls, value: object) -> object:
        return _reject_float(value, "requested_amount")

    @field_validator("requested_at")
    @classmethod
    def normalize_requested_at(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.base_currency == self.trading_currency:
            raise ValueError("an FX conversion request requires two distinct currencies")
        if self.fx_conversion_request_id != calculate_fx_conversion_request_id(self):
            raise ValueError("FX conversion request identity does not match content")
        return self


def calculate_fx_conversion_request_id(
    request: FxConversionRequest | dict[str, object],
) -> FxConversionRequestId:
    content = _normalized_decimal_content(
        request, "fx_conversion_request_id", ("requested_amount",)
    )
    return FxConversionRequestId.parse(sha256_content_id_v2(content))


class FxConversionReservation(BaseModel):
    """A distinct FX-specific capital reservation -- deliberately not
    `risk.models.CapitalReservation`. This reserves a currency amount for
    conversion, never a trade: it carries no `instrument_id`,
    `approved_quantity`, or `reserved_downside`, none of which describe
    "reserve X units of currency Y for conversion."

    Reuses `CapitalReservation`'s proven safety shape otherwise: ownership
    fields, the same `risk.models.ReservationState` lifecycle enum, the same
    expiry-after-creation and transition-time invariants (including that an
    `ACTIVE` reservation's `transitioned_at` must equal its `created_at`),
    and the same content-identity pattern that excludes the mutable
    `state`/`transitioned_at` fields so identity is fixed at creation while
    lifecycle state can transition later.

    This type does not itself reserve anything: no capital coordinator
    consumes it, and constructing one changes no allocation, cash, or
    balance anywhere. It is pure evidence of a proposed reservation, to be
    interpreted by a future, separately authorized posting engine.

    `authority_context` can never carry `ExecutionEnvironment.LIVE`. This
    project's standing rule -- that `FULL_AUTO` never implies `LIVE`, and
    that live capital requires its own separate authorization -- is enforced
    here at construction time regardless of `approval_policy`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fx_conversion_reservation_id: FxConversionReservationId
    schema_version: Literal["fx-conversion-reservation-v1"] = "fx-conversion-reservation-v1"
    request: FxConversionRequest
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    base_currency: str = Field(min_length=3, max_length=3, pattern=_CURRENCY_PATTERN)
    reserved_amount: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    authority_context: ExecutionDimensions
    created_at: datetime
    expires_at: datetime
    state: ReservationState = ReservationState.ACTIVE
    transitioned_at: datetime

    @field_validator("reserved_amount", mode="before")
    @classmethod
    def reject_float_reserved_amount(cls, value: object) -> object:
        return _reject_float(value, "reserved_amount")

    @field_validator("created_at", "expires_at", "transitioned_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_reservation(self) -> Self:
        if self.account_id != self.request.account_id:
            raise ValueError("reservation account_id does not match its request")
        if self.allocation_id != self.request.allocation_id:
            raise ValueError("reservation allocation_id does not match its request")
        if self.agent_id != self.request.agent_id:
            raise ValueError("reservation agent_id does not match its request")
        if self.base_currency != self.request.base_currency:
            raise ValueError("reservation base_currency does not match its request")
        if self.reserved_amount != self.request.requested_amount:
            raise ValueError("reservation reserved_amount does not match its request")
        if self.authority_context.execution_environment is ExecutionEnvironment.LIVE:
            raise ValueError("an FX conversion reservation cannot authorize LIVE execution")
        if self.expires_at <= self.created_at:
            raise ValueError("reservation expiry must follow creation")
        if self.transitioned_at < self.created_at:
            raise ValueError("reservation transition cannot predate creation")
        if self.state is ReservationState.ACTIVE and self.transitioned_at != self.created_at:
            raise ValueError("active reservation transition time must equal creation time")
        if self.fx_conversion_reservation_id != calculate_fx_conversion_reservation_id(self):
            raise ValueError("FX conversion reservation identity does not match content")
        return self


def _fx_conversion_reservation_identity_content(
    reservation: FxConversionReservation | dict[str, object],
) -> dict[str, object]:
    content = _normalized_decimal_content(
        reservation, "fx_conversion_reservation_id", ("reserved_amount",)
    )
    for field in ("state", "transitioned_at"):
        content.pop(field, None)
    return content


def calculate_fx_conversion_reservation_id(
    reservation: FxConversionReservation | dict[str, object],
) -> FxConversionReservationId:
    return FxConversionReservationId.parse(
        sha256_content_id_v2(_fx_conversion_reservation_identity_content(reservation))
    )


class FxConversionAuthorization(BaseModel):
    """Immutable evidence that one `FxConversionCalculation` was authorized
    against one specific, still-`ACTIVE` `FxConversionReservation`, under
    one explicit `authority_context`.

    A permission record, not proof that anything was posted: it embeds the
    calculation's complete validated content (there is no separate identity
    for `FxConversionCalculation` to reference instead -- see its own
    docstring for why) and the reservation's complete content, and
    structurally forbids authorizing a different amount or currency pair
    than what was actually reserved. Constructing one moves no capital and
    mutates no balance or allocation state.

    `authority_context` is its own, independent field rather than being
    required to equal `reservation.authority_context` in full: time passes
    between reservation and authorization, and a real system would
    re-evaluate authority fresh at the later point rather than only trusting
    what was true earlier (the same "recheck, don't only trust" pattern
    `select_eligible_fx_observation` already applies to causal eligibility
    in `simulation.fx`). This "refresh" is deliberately narrow, not a
    blanket exemption: `approval_policy` and `execution_environment` --
    the two dimensions that determine *whether* this conversion is approved
    to proceed and under what capital-risk regime -- must agree exactly
    with the reservation's; any other dimension (`data_run_mode`,
    `submission_mode`, `operating_context`, `experiment_id`,
    `experiment_type`) may legitimately differ, since those describe
    surrounding operational context rather than the approval itself. A
    mismatch on `approval_policy` or `execution_environment` is rejected
    outright rather than resolved by treating either record as more
    authoritative than the other -- neither this type nor
    `FxConversionReservation` establishes any such precedence, so
    disagreement is always a hard error, never a silently-broken tie.
    `execution_environment` additionally, and independently, repeats the
    never-`LIVE` check `FxConversionReservation` already enforces, as
    defense-in-depth.

    One limitation, recorded here for reviewers: this type validates that
    `calculation`'s own fields are internally exact and self-consistent (via
    `FxConversionCalculation`'s own validators), and that it agrees with the
    reservation on amount and currency pair. It cannot prove that
    `calculation` was actually produced by a legitimate call to
    `calculate_fx_conversion` (with real V2/BID/causal-eligibility
    enforcement) rather than hand-constructed to bypass that boundary --
    `FxConversionCalculation` has no field recording its own provenance and
    is directly constructible by any caller. This is the same trust
    assumption `RiskEvaluationState` already makes about its embedded
    snapshots; it is not a new or hidden weakening, but it should be
    understood before this evidence is relied upon by anything that acts on
    it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fx_conversion_authorization_id: FxConversionAuthorizationId
    schema_version: Literal["fx-conversion-authorization-v1"] = "fx-conversion-authorization-v1"
    reservation: FxConversionReservation
    calculation: FxConversionCalculation
    authority_context: ExecutionDimensions
    authorized_at: datetime

    @field_validator("authorized_at")
    @classmethod
    def normalize_authorized_at(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @property
    def account_id(self) -> AccountId:
        return self.reservation.account_id

    @property
    def allocation_id(self) -> AllocationId:
        return self.reservation.allocation_id

    @property
    def agent_id(self) -> AgentId:
        return self.reservation.agent_id

    @model_validator(mode="after")
    def validate_authorization(self) -> Self:
        if self.reservation.state is not ReservationState.ACTIVE:
            raise ValueError(
                "an FX conversion can only be authorized against an ACTIVE reservation"
            )
        if self.authority_context.execution_environment is ExecutionEnvironment.LIVE:
            raise ValueError("an FX conversion authorization cannot enable LIVE execution")
        if (
            self.authority_context.approval_policy
            != self.reservation.authority_context.approval_policy
        ):
            raise ValueError(
                "authorization approval_policy does not match the reservation's "
                "approval_policy; reservation and authorization must not silently "
                "disagree about the policy governing this conversion"
            )
        if (
            self.authority_context.execution_environment
            != self.reservation.authority_context.execution_environment
        ):
            raise ValueError(
                "authorization execution_environment does not match the reservation's "
                "execution_environment"
            )
        if self.calculation.base_currency != self.reservation.base_currency:
            raise ValueError("authorized calculation base_currency does not match its reservation")
        if self.calculation.trading_currency != self.reservation.request.trading_currency:
            raise ValueError(
                "authorized calculation trading_currency does not match the original request"
            )
        if self.calculation.base_amount != self.reservation.reserved_amount:
            raise ValueError(
                "authorized calculation base_amount does not match the reserved amount"
            )
        if not (self.reservation.created_at <= self.authorized_at < self.reservation.expires_at):
            raise ValueError(
                "authorization time must fall within the reservation's validity window"
            )
        if self.fx_conversion_authorization_id != calculate_fx_conversion_authorization_id(self):
            raise ValueError("FX conversion authorization identity does not match content")
        return self


def calculate_fx_conversion_authorization_id(
    authorization: FxConversionAuthorization | dict[str, object],
) -> FxConversionAuthorizationId:
    content = _identity_content(authorization, "fx_conversion_authorization_id")
    return FxConversionAuthorizationId.parse(sha256_content_id_v2(content))


class FxConversionPostingIneligibleReason(StrEnum):
    """Typed reason a proposed FX conversion posting could not be evaluated as eligible."""

    ZERO_ROUNDED_TRADING_AMOUNT = "ZERO_ROUNDED_TRADING_AMOUNT"


class FxConversionPostingIneligible(BaseModel):
    """Pure typed evidence that an authorized FX conversion calculation does
    not qualify for posting evidence. A plain return value, not
    content-identified -- mirrors `FxConversionQuoteUnavailable`/
    `FxObservationUnavailable` in `simulation.fx` for the same reason: this
    is a legitimate, correctly-computed outcome, not a malformed input.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: FxConversionPostingIneligibleReason
    fx_conversion_authorization_id: FxConversionAuthorizationId


class FxConversionPostingEvidence(BaseModel):
    """Immutable, self-contained evidence of what a completed FX conversion
    posting would consist of, for one authorized, posting-eligible
    calculation.

    This is *proposed* posting evidence, not proof that any cash, balance,
    allocation, or ledger was actually mutated. No such mutation is
    implemented anywhere in this module, and constructing this record has no
    side effect. A future, separately authorized posting engine -- and a
    separate, not-yet-made decision on ledger architecture -- is what would
    give this evidence operational meaning.

    Embeds `authorization` in full (which transitively embeds the
    reservation and the complete calculation), so the entire audit trail --
    request, reservation, authorization, calculation -- is reconstructable
    from this one record alone.

    Preserves `exact_trading_amount` and `rounded_trading_amount` exactly as
    the embedded calculation produced them. The rounding residual
    (`exact_trading_amount - rounded_trading_amount`) is intentionally *not*
    stored as its own field: it is always derivable from the two preserved
    amounts, and is exposed only as the read-only `rounding_residual`
    property below, never as part of this model's own schema or content
    identity. This is a deliberate design choice: the residual is a
    discretization artifact of expressing an exact real-valued calculation
    in a currency's finite minor-unit granularity, not a fee, not a
    liability, and not cash. Storing it as its own field -- let alone a
    clearing/suspense account -- would imply an economic claim that does not
    exist. Its sign is not fixed: rounding can move value in either
    direction depending on where the true product falls relative to the
    minor-unit boundary.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fx_conversion_posting_evidence_id: FxConversionPostingEvidenceId
    schema_version: Literal["fx-conversion-posting-evidence-v1"] = (
        "fx-conversion-posting-evidence-v1"
    )
    authorization: FxConversionAuthorization
    base_currency_minor_unit_digits: Annotated[int, Field(ge=0)]
    evaluated_at: datetime

    @field_validator("base_currency_minor_unit_digits", mode="before")
    @classmethod
    def reject_non_genuine_int_base_minor_unit_digits(cls, value: object) -> object:
        return validate_minor_unit_digits(value, field_name="base_currency_minor_unit_digits")

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @property
    def account_id(self) -> AccountId:
        return self.authorization.account_id

    @property
    def allocation_id(self) -> AllocationId:
        return self.authorization.allocation_id

    @property
    def agent_id(self) -> AgentId:
        return self.authorization.agent_id

    @property
    def rounding_residual(self) -> Decimal:
        """`exact_trading_amount - rounded_trading_amount`, always
        re-derivable from the two preserved amounts on the embedded
        calculation, never itself stored, identified, or booked as a
        balance."""
        return (
            self.authorization.calculation.exact_trading_amount
            - self.authorization.calculation.rounded_trading_amount
        )

    @model_validator(mode="after")
    def validate_posting_evidence(self) -> Self:
        if self.authorization.calculation.rounded_trading_amount == 0:
            raise ValueError(
                "posting evidence cannot be constructed for a zero rounded_trading_amount; "
                "use evaluate_fx_conversion_posting_eligibility instead of constructing this "
                "type directly"
            )
        if not _base_amount_conforms_to_minor_unit_digits(
            self.authorization.calculation.base_amount, self.base_currency_minor_unit_digits
        ):
            raise ValueError("base_amount does not conform to base_currency_minor_unit_digits")
        if self.evaluated_at < self.authorization.authorized_at:
            raise ValueError("posting evidence cannot be evaluated before its authorization")
        if self.fx_conversion_posting_evidence_id != calculate_fx_conversion_posting_evidence_id(
            self
        ):
            raise ValueError("FX conversion posting evidence identity does not match content")
        return self


def calculate_fx_conversion_posting_evidence_id(
    evidence: FxConversionPostingEvidence | dict[str, object],
) -> FxConversionPostingEvidenceId:
    content = _identity_content(evidence, "fx_conversion_posting_evidence_id")
    return FxConversionPostingEvidenceId.parse(sha256_content_id_v2(content))


def evaluate_fx_conversion_posting_eligibility(
    authorization: FxConversionAuthorization,
    base_currency_minor_unit_digits: int,
    evaluated_at: datetime,
) -> FxConversionPostingEvidence | FxConversionPostingIneligible:
    """Pure evaluation of whether an authorized FX conversion calculation is
    eligible to have posting evidence recorded for it. Computes no
    conversion, moves no capital, and mutates nothing.

    Does not change `calculate_fx_conversion`/`FxConversionCalculation`'s
    existing ability to return a zero `rounded_trading_amount` -- that
    remains a valid, unmodified calculation outcome. This function adds a
    separate, later posting-eligibility gate: a zero rounded_trading_amount
    is a legitimate calculation but is never eligible for posting evidence,
    since debiting the base currency for a zero-value credit is never a
    valid conversion. Returns typed `FxConversionPostingIneligible` evidence
    for this case, mirroring `FxConversionQuoteUnavailable`'s established
    typed-evidence-vs-raised-error split in `simulation.fx`.

    Raises `FxConversionInputError` (imported unchanged from `simulation.fx`)
    for a malformed `base_currency_minor_unit_digits` (not a genuine
    non-negative int) or a `base_amount` that does not already conform to
    that many decimal digits -- both are caller/configuration errors, not
    data-availability or business outcomes, matching the same distinction
    `FxConversionPolicyUnsupportedError`/`FxConversionInputError` already
    draw elsewhere in this project's FX contracts. Never hardcodes a
    currency-specific precision (e.g. EUR's conventional two digits): the
    caller must always state it explicitly.
    """
    base_currency_minor_unit_digits = validate_minor_unit_digits(
        base_currency_minor_unit_digits, field_name="base_currency_minor_unit_digits"
    )
    if not _base_amount_conforms_to_minor_unit_digits(
        authorization.calculation.base_amount, base_currency_minor_unit_digits
    ):
        raise FxConversionInputError(
            "base_amount does not conform to base_currency_minor_unit_digits"
        )
    if authorization.calculation.rounded_trading_amount == 0:
        return FxConversionPostingIneligible(
            reason=FxConversionPostingIneligibleReason.ZERO_ROUNDED_TRADING_AMOUNT,
            fx_conversion_authorization_id=authorization.fx_conversion_authorization_id,
        )
    normalized_evaluated_at = _aware_utc(evaluated_at)
    content: dict[str, object] = {
        "schema_version": "fx-conversion-posting-evidence-v1",
        "authorization": authorization,
        "base_currency_minor_unit_digits": base_currency_minor_unit_digits,
        "evaluated_at": normalized_evaluated_at,
    }
    return FxConversionPostingEvidence.model_validate(
        {
            "fx_conversion_posting_evidence_id": calculate_fx_conversion_posting_evidence_id(
                content
            ),
            **content,
        }
    )
