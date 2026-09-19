"""Behavior tests for the Phase 6.2 pure FX conversion reservation,
authorization and posting-evidence contracts.

These contracts are pure and evidence-only, exactly like
`ai_trading_scanner.simulation.fx`: constructing any type here has no side
effect. No capital coordinator, cash ledger, or balance mutation exists
anywhere in this test file or the module it tests; several tests below
assert that boundary explicitly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ai_trading_scanner.domain import (
    AccountId,
    AgentId,
    AllocationId,
    DataRunMode,
    ExecutionDimensions,
    ExecutionEnvironment,
    FxConversionAuthorizationId,
    OperatingContext,
)
from ai_trading_scanner.domain import ApprovalPolicy as _ApprovalPolicy
from ai_trading_scanner.domain import SubmissionMode as _SubmissionMode
from ai_trading_scanner.risk.models import CapitalReservation, ReservationState
from ai_trading_scanner.simulation.costs import CostRoundingPolicy
from ai_trading_scanner.simulation.fx import (
    FxConversionCalculation,
    FxConversionDirection,
    FxConversionInputError,
    FxConversionPolicyConfiguration,
    FxObservationQualityStatus,
    FxObservationReference,
    FxQuoteConvention,
    calculate_fx_conversion,
    calculate_fx_conversion_policy_id,
    calculate_fx_observation_id,
    validate_minor_unit_digits,
)
from ai_trading_scanner.simulation.fx_posting_evidence import (
    FxConversionAuthorization,
    FxConversionPostingEvidence,
    FxConversionPostingIneligible,
    FxConversionPostingIneligibleReason,
    FxConversionRequest,
    FxConversionReservation,
    calculate_fx_conversion_authorization_id,
    calculate_fx_conversion_posting_evidence_id,
    calculate_fx_conversion_request_id,
    calculate_fx_conversion_reservation_id,
    evaluate_fx_conversion_posting_eligibility,
)

_T = datetime(2026, 1, 2, 15, 0, 0, tzinfo=UTC)
_ACCOUNT_ID = AccountId("acct-1")
_ALLOCATION_ID = AllocationId("alloc-1")
_AGENT_ID = AgentId("agent-1")


def _dimensions(**changes: object) -> ExecutionDimensions:
    defaults: dict[str, object] = {
        "data_run_mode": DataRunMode.HISTORICAL_REPLAY,
        "execution_environment": ExecutionEnvironment.SIMULATION,
        "submission_mode": _SubmissionMode.SIGNAL_ONLY,
        "approval_policy": _ApprovalPolicy.FULL_AUTO,
        "operating_context": OperatingContext.NORMAL,
    }
    defaults.update(changes)
    return ExecutionDimensions(**defaults)  # type: ignore[arg-type]


def _request(**changes: object) -> FxConversionRequest:
    content: dict[str, object] = {
        "schema_version": "fx-conversion-request-v1",
        "account_id": _ACCOUNT_ID,
        "allocation_id": _ALLOCATION_ID,
        "agent_id": _AGENT_ID,
        "base_currency": "EUR",
        "trading_currency": "USD",
        "requested_amount": Decimal("50.00"),
        "requested_at": _T,
    }
    content.update(changes)
    return FxConversionRequest.model_validate(
        {"fx_conversion_request_id": calculate_fx_conversion_request_id(content), **content}
    )


def _reservation(
    request: FxConversionRequest | None = None, **changes: object
) -> FxConversionReservation:
    request = request or _request()
    content: dict[str, object] = {
        "schema_version": "fx-conversion-reservation-v1",
        "request": request,
        "account_id": request.account_id,
        "allocation_id": request.allocation_id,
        "agent_id": request.agent_id,
        "base_currency": request.base_currency,
        "reserved_amount": request.requested_amount,
        "authority_context": _dimensions(),
        "created_at": _T,
        "expires_at": _T + timedelta(minutes=5),
        "transitioned_at": _T,
    }
    content.update(changes)
    return FxConversionReservation.model_validate(
        {
            "fx_conversion_reservation_id": calculate_fx_conversion_reservation_id(content),
            **content,
        }
    )


def _policy(**changes: object) -> FxConversionPolicyConfiguration:
    content: dict[str, object] = {
        "schema_version": "fx-conversion-policy-v2",
        "policy_name": "TEST_ONLY_INITIAL_CONVERSION",
        "model_version": "test-only-v1",
        "base_currency": "EUR",
        "trading_currency": "USD",
        "quote_convention": FxQuoteConvention.BID,
        "maximum_observation_staleness_seconds": 60,
        "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
        "conversion_direction": FxConversionDirection.SELL_BASE_FOR_TRADING,
    }
    content.update(changes)
    return FxConversionPolicyConfiguration.model_validate(
        {"fx_conversion_policy_id": calculate_fx_conversion_policy_id(content), **content}
    )


def _observation(**changes: object) -> FxObservationReference:
    content: dict[str, object] = {
        "schema_version": "fx-observation-reference-v1",
        "base_currency": "EUR",
        "quote_currency": "USD",
        "provider": "TEST_ONLY_SYNTHETIC_PROVIDER",
        "methodology_version": "test-only-v1",
        "quote_convention": FxQuoteConvention.BID,
        "rate": "1.10",
        "observed_at": _T - timedelta(seconds=30),
        "available_at": _T - timedelta(seconds=10),
        "source_dataset_id": "TEST_ONLY_SYNTHETIC_FX_DATASET",
        "source_dataset_version": "test-only-v1",
        "source_record_id": "fx:test-only:1",
        "source_checksum": None,
        "ingestion_provenance": "TEST_ONLY: manual synthetic fixture, not a real ingestion run",
        "quality_status": FxObservationQualityStatus.VALIDATED,
    }
    content.update(changes)
    return FxObservationReference.model_validate(
        {"fx_observation_id": calculate_fx_observation_id(content), **content}
    )


def _authorization(
    reservation: FxConversionReservation | None = None,
    *,
    rate: str = "1.10",
    minor_unit_digits: int = 2,
    **changes: object,
) -> FxConversionAuthorization:
    reservation = reservation or _reservation()
    observation = _observation(rate=rate)
    policy = _policy(
        base_currency=reservation.base_currency,
        trading_currency=reservation.request.trading_currency,
    )
    calculation = calculate_fx_conversion(
        [observation], policy, reservation.reserved_amount, minor_unit_digits, _T
    )
    assert isinstance(calculation, FxConversionCalculation), "expected a successful calculation"
    content: dict[str, object] = {
        "schema_version": "fx-conversion-authorization-v1",
        "reservation": reservation,
        "calculation": calculation,
        "authority_context": reservation.authority_context,
        "authorized_at": _T,
    }
    content.update(changes)
    return FxConversionAuthorization.model_validate(
        {
            "fx_conversion_authorization_id": calculate_fx_conversion_authorization_id(content),
            **content,
        }
    )


# --- FxConversionRequest -----------------------------------------------


def test_request_identity_gives_natural_idempotency_for_identical_resubmission() -> None:
    first = _request()
    second = _request()
    assert first.fx_conversion_request_id == second.fx_conversion_request_id
    assert first == second


def test_request_identity_differs_for_different_amount() -> None:
    first = _request(requested_amount=Decimal("50.00"))
    second = _request(requested_amount=Decimal("50.01"))
    assert first.fx_conversion_request_id != second.fx_conversion_request_id


def test_request_identity_differs_for_different_requested_at() -> None:
    first = _request(requested_at=_T)
    second = _request(requested_at=_T + timedelta(seconds=1))
    assert first.fx_conversion_request_id != second.fx_conversion_request_id


def test_request_identity_is_independent_of_trade_proposal_id() -> None:
    """FxConversionRequestId is its own identity domain -- no TradeProposalId
    field exists anywhere on FxConversionRequest."""
    assert "proposal_id" not in FxConversionRequest.model_fields
    assert "trade_proposal_id" not in FxConversionRequest.model_fields


def test_request_requires_two_distinct_currencies() -> None:
    with pytest.raises(ValidationError, match="two distinct currencies"):
        _request(base_currency="EUR", trading_currency="EUR")


def test_request_rejects_float_requested_amount() -> None:
    content: dict[str, object] = {
        "schema_version": "fx-conversion-request-v1",
        "account_id": _ACCOUNT_ID,
        "allocation_id": _ALLOCATION_ID,
        "agent_id": _AGENT_ID,
        "base_currency": "EUR",
        "trading_currency": "USD",
        "requested_amount": 50.0,
        "requested_at": _T,
    }
    with pytest.raises(ValidationError, match="float"):
        FxConversionRequest.model_validate(
            {"fx_conversion_request_id": "sha256:" + "0" * 64, **content}
        )


# --- FxConversionReservation ---------------------------------------------


def test_reservation_carries_no_trade_specific_fields() -> None:
    """Item 1: distinct from CapitalReservation -- no instrument_id,
    approved_quantity, or reserved_downside anywhere on this type."""
    forbidden = {"instrument_id", "approved_quantity", "reserved_downside"}
    assert forbidden.isdisjoint(FxConversionReservation.model_fields)
    assert forbidden.issubset(CapitalReservation.model_fields)


def test_reservation_reuses_the_existing_reservation_state_enum() -> None:
    reservation = _reservation()
    assert isinstance(reservation.state, ReservationState)
    assert reservation.state is ReservationState.ACTIVE


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("account_id", AccountId("acct-2")),
        ("allocation_id", AllocationId("alloc-2")),
        ("agent_id", AgentId("agent-2")),
        ("base_currency", "GBP"),
    ],
)
def test_reservation_rejects_ownership_or_currency_mismatch_against_request(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError, match="does not match its request"):
        _reservation(**{field: value})  # type: ignore[arg-type]


def test_reservation_rejects_amount_mismatch_against_request() -> None:
    with pytest.raises(ValidationError, match="reserved_amount does not match its request"):
        _reservation(reserved_amount=Decimal("49.00"))


def test_reservation_cannot_authorize_live_execution() -> None:
    """Item 2: FULL_AUTO never implies LIVE -- LIVE is rejected regardless
    of approval_policy."""
    with pytest.raises(ValidationError, match="cannot authorize LIVE execution"):
        _reservation(authority_context=_dimensions(execution_environment=ExecutionEnvironment.LIVE))


def test_reservation_active_state_requires_transitioned_at_equal_created_at() -> None:
    with pytest.raises(ValidationError, match="transition time must equal creation time"):
        _reservation(transitioned_at=_T + timedelta(seconds=1))


def test_reservation_expiry_must_follow_creation() -> None:
    with pytest.raises(ValidationError, match="expiry must follow creation"):
        _reservation(expires_at=_T)


def test_reservation_identity_excludes_state_and_transitioned_at() -> None:
    """Mirrors CapitalReservation: identity is fixed at creation and does
    not change if lifecycle state later transitions."""
    active = _reservation()
    consumed_content = active.model_dump(mode="python")
    consumed_content["state"] = ReservationState.CONSUMED
    consumed_content["transitioned_at"] = _T + timedelta(seconds=1)
    assert (
        calculate_fx_conversion_reservation_id(consumed_content)
        == active.fx_conversion_reservation_id
    )


# --- FxConversionAuthorization -------------------------------------------


def test_authorization_embeds_the_complete_calculation_content() -> None:
    """Item 4: FxConversionCalculation stays non-identity-bearing; its full
    validated content is embedded verbatim, not referenced by an id that
    does not exist."""
    authorization = _authorization()
    assert authorization.calculation.exact_trading_amount == Decimal("55.0000")
    assert authorization.calculation.rounded_trading_amount == Decimal("55.00")
    assert "fx_conversion_calculation_id" not in type(authorization.calculation).model_fields


def test_authorization_rejects_amount_mismatch_against_reservation() -> None:
    """The calculation's base_amount must equal the reservation's own
    reserved_amount -- authorizing a calculation for a different amount
    than what was actually reserved must be structurally impossible."""
    reservation = _reservation()
    observation = _observation(rate="1.10")
    policy = _policy()
    smaller_calculation = calculate_fx_conversion([observation], policy, Decimal("10.00"), 2, _T)
    assert isinstance(smaller_calculation, FxConversionCalculation)
    content: dict[str, object] = {
        "schema_version": "fx-conversion-authorization-v1",
        "reservation": reservation,
        "calculation": smaller_calculation,
        "authority_context": reservation.authority_context,
        "authorized_at": _T,
    }
    with pytest.raises(ValidationError, match="does not match the reserved amount"):
        FxConversionAuthorization.model_validate(
            {
                "fx_conversion_authorization_id": calculate_fx_conversion_authorization_id(content),
                **content,
            }
        )


def test_authorization_rejects_non_active_reservation() -> None:
    reservation = _reservation(state=ReservationState.RELEASED)
    with pytest.raises(ValidationError, match="only be authorized against an ACTIVE reservation"):
        _authorization(reservation)


def test_authorization_accepts_matching_approval_policy() -> None:
    """Requirement 1, positive case: reservation and authorization agreeing
    on approval_policy (the default helper behavior) succeeds."""
    reservation = _reservation()
    authorization = _authorization(reservation)
    assert (
        authorization.authority_context.approval_policy
        == reservation.authority_context.approval_policy
    )


def test_authorization_rejects_conflicting_approval_policy() -> None:
    """Requirement 1: reservation and authorization must not silently
    disagree about the approval policy governing the conversion. A
    reservation made under FULL_AUTO cannot be authorized under
    MANUAL_APPROVAL, or vice versa -- neither record is treated as more
    authoritative than the other; disagreement is always a hard error."""
    reservation = _reservation(
        authority_context=_dimensions(approval_policy=_ApprovalPolicy.FULL_AUTO)
    )
    with pytest.raises(ValidationError, match="approval_policy does not match"):
        _authorization(
            reservation,
            authority_context=_dimensions(approval_policy=_ApprovalPolicy.MANUAL_APPROVAL),
        )


def test_authorization_rejects_conflicting_execution_environment_even_when_neither_is_live() -> (
    None
):
    """The execution_environment compatibility check is independent of, and
    stricter than, the LIVE-only check: PAPER vs SIMULATION disagreement is
    rejected too, with its own distinct message, not silently allowed just
    because neither side is LIVE."""
    reservation = _reservation(
        authority_context=_dimensions(execution_environment=ExecutionEnvironment.SIMULATION)
    )
    with pytest.raises(ValidationError, match="execution_environment does not match"):
        _authorization(
            reservation,
            authority_context=_dimensions(execution_environment=ExecutionEnvironment.PAPER),
        )


def test_authorization_accepts_a_legitimate_refreshed_authority_context() -> None:
    """authority_context is not required to equal reservation.authority_context
    in full: a real system would re-evaluate it fresh at authorization time
    rather than only trusting what was true earlier. A refreshed context
    that keeps approval_policy and execution_environment identical to the
    reservation's, while differing on submission_mode (an operational
    dimension, not an approval dimension), is a legitimate refresh and is
    accepted."""
    reservation = _reservation()
    authorization = _authorization(
        reservation,
        authority_context=_dimensions(submission_mode=_SubmissionMode.ORDER_ENABLED),
    )
    assert authorization.authority_context != reservation.authority_context
    assert (
        authorization.authority_context.approval_policy
        == reservation.authority_context.approval_policy
    )
    assert (
        authorization.authority_context.execution_environment
        == reservation.authority_context.execution_environment
    )


def test_authorization_cannot_enable_live_execution() -> None:
    """LIVE rejection, authorization boundary (the reservation boundary is
    covered separately by test_reservation_cannot_authorize_live_execution
    above): the authorization's own authority_context independently rejects
    LIVE, regardless of what the reservation's own (necessarily non-LIVE)
    authority_context was -- defense-in-depth, not merely inherited from
    the reservation, and not superseded by the new execution_environment
    equality check (the LIVE-specific message still fires first)."""
    reservation = _reservation()
    live_dimensions = _dimensions(execution_environment=ExecutionEnvironment.LIVE)
    with pytest.raises(ValidationError, match="cannot enable LIVE execution"):
        _authorization(reservation, authority_context=live_dimensions)


def test_authorization_ownership_is_unaffected_by_a_refreshed_authority_context() -> None:
    """Ownership guarantees (item 3): account_id/allocation_id/agent_id are
    read-only properties derived solely from the embedded reservation, never
    from authority_context -- a legitimately refreshed authority_context
    changes nothing about ownership."""
    reservation = _reservation()
    authorization = _authorization(
        reservation,
        authority_context=_dimensions(submission_mode=_SubmissionMode.ORDER_ENABLED),
    )
    assert authorization.account_id == reservation.account_id == _ACCOUNT_ID
    assert authorization.allocation_id == reservation.allocation_id == _ALLOCATION_ID
    assert authorization.agent_id == reservation.agent_id == _AGENT_ID
    assert "account_id" not in FxConversionAuthorization.model_fields
    assert "allocation_id" not in FxConversionAuthorization.model_fields
    assert "agent_id" not in FxConversionAuthorization.model_fields


def test_authorization_rejects_time_outside_reservation_window() -> None:
    reservation = _reservation()
    with pytest.raises(ValidationError, match="validity window"):
        _authorization(reservation, authorized_at=reservation.expires_at)


def test_authorization_exposes_ownership_via_reservation() -> None:
    authorization = _authorization()
    assert authorization.account_id == _ACCOUNT_ID
    assert authorization.allocation_id == _ALLOCATION_ID
    assert authorization.agent_id == _AGENT_ID


# --- evaluate_fx_conversion_posting_eligibility / FxConversionPostingEvidence --


def test_posting_evidence_preserves_exact_and_rounded_amounts() -> None:
    """Item 7: both amounts preserved verbatim from the embedded calculation."""
    authorization = _authorization(rate="1.10")
    evidence = evaluate_fx_conversion_posting_eligibility(authorization, 2, _T)
    assert isinstance(evidence, FxConversionPostingEvidence)
    assert evidence.authorization.calculation.exact_trading_amount == Decimal("55.0000")
    assert evidence.authorization.calculation.rounded_trading_amount == Decimal("55.00")
    assert evidence.rounding_residual == Decimal("0.0000")


def test_posting_evidence_nonzero_residual_is_derivable_not_stored() -> None:
    """Second walkthrough scenario: rate 1.08375 on EUR 100 produces a
    negative residual (more USD credited than the exact math justifies),
    proving the residual is not always a loss and is never a stored field."""
    reservation = _reservation(
        request=_request(requested_amount=Decimal("100.00")),
        reserved_amount=Decimal("100.00"),
    )
    authorization = _authorization(reservation, rate="1.08375")
    evidence = evaluate_fx_conversion_posting_eligibility(authorization, 2, _T)
    assert isinstance(evidence, FxConversionPostingEvidence)
    assert evidence.authorization.calculation.exact_trading_amount == Decimal("108.37500")
    assert evidence.authorization.calculation.rounded_trading_amount == Decimal("108.38")
    assert evidence.rounding_residual == Decimal("-0.00500")
    assert "rounding_residual" not in type(evidence).model_fields


def test_posting_evidence_does_not_create_a_clearing_account_fee_or_liability() -> None:
    """Item 7: structural proof -- no field name suggests a clearing
    account, fee, or liability anywhere on this contract."""
    forbidden_substrings = ("clearing", "suspense", "fee", "liability", "commission", "spread")
    for field_name in FxConversionPostingEvidence.model_fields:
        lowered = field_name.lower()
        assert not any(substring in lowered for substring in forbidden_substrings), field_name


def test_posting_evidence_never_claims_a_cash_movement_occurred() -> None:
    forbidden_substrings = ("balance", "capital", "debit", "credit", "posted", "executed", "ledger")
    for field_name in FxConversionPostingEvidence.model_fields:
        lowered = field_name.lower()
        assert not any(substring in lowered for substring in forbidden_substrings), field_name


def test_posting_ineligible_when_rounded_trading_amount_is_zero() -> None:
    """Item 6: reject posting eligibility for a zero rounded_trading_amount."""
    reservation = _reservation(
        request=_request(requested_amount=Decimal("0.01")),
        reserved_amount=Decimal("0.01"),
    )
    authorization = _authorization(reservation, rate="0.001", minor_unit_digits=2)
    assert authorization.calculation.rounded_trading_amount == Decimal("0.00")
    result = evaluate_fx_conversion_posting_eligibility(authorization, 2, _T)
    assert isinstance(result, FxConversionPostingIneligible)
    assert result.reason is FxConversionPostingIneligibleReason.ZERO_ROUNDED_TRADING_AMOUNT
    assert result.fx_conversion_authorization_id == authorization.fx_conversion_authorization_id


def test_calculate_fx_conversion_can_still_return_a_zero_rounded_amount() -> None:
    """Item 6 explicitly preserves this: the pure calculation layer itself
    is unmodified and must still be able to produce a zero credit."""
    observation = _observation(rate="0.001")
    policy = _policy()
    calculation = calculate_fx_conversion([observation], policy, Decimal("0.01"), 2, _T)
    assert isinstance(calculation, FxConversionCalculation)
    assert calculation.rounded_trading_amount == Decimal("0.00")


def test_posting_evidence_direct_construction_also_rejects_zero_rounded_amount() -> None:
    """Defense-in-depth: the type's own validator, not just the evaluation
    function, refuses to represent an ineligible state."""
    reservation = _reservation(
        request=_request(requested_amount=Decimal("0.01")),
        reserved_amount=Decimal("0.01"),
    )
    authorization = _authorization(reservation, rate="0.001", minor_unit_digits=2)
    content: dict[str, object] = {
        "schema_version": "fx-conversion-posting-evidence-v1",
        "authorization": authorization,
        "base_currency_minor_unit_digits": 2,
        "evaluated_at": _T,
    }
    with pytest.raises(ValidationError, match="zero rounded_trading_amount"):
        FxConversionPostingEvidence.model_validate(
            {
                "fx_conversion_posting_evidence_id": calculate_fx_conversion_posting_evidence_id(
                    content
                ),
                **content,
            }
        )


def test_posting_eligibility_requires_base_amount_conforming_to_registered_minor_units() -> None:
    """Item 5: no hardcoded EUR precision -- the caller must state
    base_currency_minor_unit_digits explicitly, and an amount with more
    precision than that is rejected."""
    reservation = _reservation(
        request=_request(requested_amount=Decimal("50.005")),
        reserved_amount=Decimal("50.005"),
    )
    authorization = _authorization(reservation, rate="1.10")
    with pytest.raises(FxConversionInputError, match="does not conform"):
        evaluate_fx_conversion_posting_eligibility(authorization, 2, _T)


def test_posting_eligibility_accepts_base_amount_conforming_to_zero_minor_units() -> None:
    """No two-decimal-place assumption on the base currency either: a
    0-minor-unit base currency amount is accepted when it genuinely has no
    fractional part."""
    reservation = _reservation(
        request=_request(requested_amount=Decimal("50")),
        reserved_amount=Decimal("50"),
    )
    authorization = _authorization(reservation, rate="1.10")
    evidence = evaluate_fx_conversion_posting_eligibility(authorization, 0, _T)
    assert isinstance(evidence, FxConversionPostingEvidence)
    assert evidence.base_currency_minor_unit_digits == 0


@pytest.mark.parametrize(
    "invalid_digits",
    [True, False, 2.5, "2", None, -1],
)
def test_posting_eligibility_rejects_non_genuine_int_base_minor_unit_digits(
    invalid_digits: object,
) -> None:
    authorization = _authorization()
    with pytest.raises(FxConversionInputError):
        evaluate_fx_conversion_posting_eligibility(authorization, invalid_digits, _T)  # type: ignore[arg-type]


def test_validate_minor_unit_digits_is_reused_not_duplicated() -> None:
    """The same helper simulation.fx already uses for
    trading_currency_minor_unit_digits is reused here for
    base_currency_minor_unit_digits, rather than a second, independent copy
    of the same rule."""
    with pytest.raises(FxConversionInputError, match="base_currency_minor_unit_digits"):
        validate_minor_unit_digits(True, field_name="base_currency_minor_unit_digits")


def test_posting_evidence_identity_is_independent_of_evaluation_time() -> None:
    """Two evaluations of the same authorization at different evaluated_at
    instants are two distinct, independently identified pieces of evidence."""
    authorization = _authorization()
    first = evaluate_fx_conversion_posting_eligibility(authorization, 2, _T)
    second = evaluate_fx_conversion_posting_eligibility(authorization, 2, _T + timedelta(seconds=1))
    assert isinstance(first, FxConversionPostingEvidence)
    assert isinstance(second, FxConversionPostingEvidence)
    assert first.fx_conversion_posting_evidence_id != second.fx_conversion_posting_evidence_id


def test_posting_evidence_reevaluation_at_the_same_instant_is_deterministic() -> None:
    """Idempotent-in-effect: re-evaluating the same authorization at the
    same instant reproduces identical evidence, not a second distinct one."""
    authorization = _authorization()
    first = evaluate_fx_conversion_posting_eligibility(authorization, 2, _T)
    second = evaluate_fx_conversion_posting_eligibility(authorization, 2, _T)
    assert first == second


def test_posting_evidence_exposes_ownership_transitively() -> None:
    authorization = _authorization()
    evidence = evaluate_fx_conversion_posting_eligibility(authorization, 2, _T)
    assert isinstance(evidence, FxConversionPostingEvidence)
    assert evidence.account_id == _ACCOUNT_ID
    assert evidence.allocation_id == _ALLOCATION_ID
    assert evidence.agent_id == _AGENT_ID


def test_posting_ineligible_is_not_content_identified() -> None:
    """Mirrors FxConversionQuoteUnavailable/FxObservationUnavailable: a
    plain return value, not an identified record."""
    assert "fx_conversion_posting_ineligible_id" not in FxConversionPostingIneligible.model_fields


def test_fx_conversion_authorization_id_is_a_distinct_identity_domain() -> None:
    authorization = _authorization()
    assert isinstance(authorization.fx_conversion_authorization_id, FxConversionAuthorizationId)


# --- No mutation anywhere in this module ------------------------------------


def test_module_defines_no_capital_coordinator_or_mutation_entrypoint() -> None:
    import ai_trading_scanner.simulation.fx_posting_evidence as module

    forbidden_names = {"consume", "release", "expire", "reserve", "post", "debit", "credit"}
    public_callables = {
        name for name in dir(module) if not name.startswith("_") and callable(getattr(module, name))
    }
    assert forbidden_names.isdisjoint({name.lower() for name in public_callables})
