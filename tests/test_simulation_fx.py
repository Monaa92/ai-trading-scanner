"""Behavior tests for the Phase 6.2 FX observation, conversion/valuation-policy,
source-checksum and pure observation-selection contracts (causal-only and
quote-side-aware).

The observation/policy contracts are pure evidence/policy shapes: no FX rate,
quote convention or staleness threshold has an engine default. Selection is
pure filtering only — no actual conversion arithmetic, balanced-leg
calculation, capital movement or manifest binding; several tests below
assert that boundary explicitly.
"""

from __future__ import annotations

import inspect
import re
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

import pytest
from pydantic import ValidationError

from ai_trading_scanner.domain import FxConversionPolicyId, FxObservationId, FxValuationPolicyId
from ai_trading_scanner.simulation import (
    CostRoundingPolicy,
    FxConversionCalculation,
    FxConversionDirection,
    FxConversionInputError,
    FxConversionPolicyConfiguration,
    FxConversionPolicyUnsupportedError,
    FxConversionQuoteUnavailable,
    FxObservationQualityStatus,
    FxObservationReference,
    FxObservationUnavailable,
    FxObservationUnavailableReason,
    FxQuoteConvention,
    FxQuoteUnavailableReason,
    FxValuationPolicyConfiguration,
    FxValuationQuoteUnavailable,
    calculate_fx_conversion,
    calculate_fx_conversion_policy_id,
    calculate_fx_observation_id,
    calculate_fx_source_checksum,
    calculate_fx_valuation_policy_id,
    select_eligible_fx_observation,
    select_eligible_fx_observation_for_conversion,
    select_eligible_fx_observation_for_valuation,
)
from ai_trading_scanner.simulation import fx as fx_module

_OBSERVED_AT = datetime(2026, 1, 2, 14, 30, tzinfo=UTC)
_AVAILABLE_AT = datetime(2026, 1, 2, 14, 30, 5, tzinfo=UTC)


def _observation(**changes: object) -> FxObservationReference:
    content: dict[str, object] = {
        "schema_version": "fx-observation-reference-v1",
        "base_currency": "EUR",
        "quote_currency": "USD",
        "provider": "TEST_ONLY_SYNTHETIC_PROVIDER",
        "methodology_version": "test-only-v1",
        "quote_convention": FxQuoteConvention.DECLARED_REFERENCE,
        "rate": "1.08",
        "observed_at": _OBSERVED_AT,
        "available_at": _AVAILABLE_AT,
        "source_dataset_id": "TEST_ONLY_SYNTHETIC_FX_DATASET",
        "source_dataset_version": "test-only-v1",
        "source_record_id": "fx:test-only:1",
        "source_checksum": None,
        "ingestion_provenance": "TEST_ONLY: manual synthetic fixture, not a real ingestion run",
        "quality_status": FxObservationQualityStatus.UNVALIDATED,
    }
    content.update(changes)
    return FxObservationReference.model_validate(
        {"fx_observation_id": calculate_fx_observation_id(content), **content}
    )


def _policy(**changes: object) -> FxConversionPolicyConfiguration:
    content: dict[str, object] = {
        "schema_version": "fx-conversion-policy-v1",
        "policy_name": "INITIAL_CONVERSION_AND_REPORTING_MARK_V1",
        "model_version": "test-only-v1",
        "base_currency": "EUR",
        "trading_currency": "USD",
        "quote_convention": FxQuoteConvention.DECLARED_REFERENCE,
        "maximum_observation_staleness_seconds": 60,
        "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
    }
    content.update(changes)
    return FxConversionPolicyConfiguration.model_validate(
        {"fx_conversion_policy_id": calculate_fx_conversion_policy_id(content), **content}
    )


# --- FxObservationReference -------------------------------------------------


def test_observation_cannot_be_available_before_it_was_observed() -> None:
    with pytest.raises(ValidationError, match="cannot be available before"):
        _observation(observed_at=_AVAILABLE_AT, available_at=_OBSERVED_AT)


def test_observation_may_be_available_at_the_same_instant_it_was_observed() -> None:
    observation = _observation(observed_at=_OBSERVED_AT, available_at=_OBSERVED_AT)
    assert observation.available_at == observation.observed_at


def test_observation_requires_two_distinct_currencies() -> None:
    with pytest.raises(ValidationError, match="two distinct currencies"):
        _observation(base_currency="EUR", quote_currency="EUR")


def test_observation_rejects_float_rate() -> None:
    """The model's own field validator rejects a float rate independently of the
    free-standing `calculate_fx_observation_id` helper (see Finding-3 tests below)."""
    content = _complete_observation_content()
    content["rate"] = 1.08
    with pytest.raises(ValidationError, match="Decimal"):
        FxObservationReference.model_validate(
            {"fx_observation_id": "sha256:" + "0" * 64, **content}
        )


def test_observation_rejects_non_positive_rate() -> None:
    with pytest.raises(ValidationError):
        _observation(rate="0")
    with pytest.raises(ValidationError):
        _observation(rate="-1.08")


def _complete_observation_content() -> dict[str, object]:
    return {
        "schema_version": "fx-observation-reference-v1",
        "base_currency": "EUR",
        "quote_currency": "USD",
        "provider": "TEST_ONLY_SYNTHETIC_PROVIDER",
        "methodology_version": "test-only-v1",
        "quote_convention": FxQuoteConvention.DECLARED_REFERENCE,
        "rate": "1.08",
        "observed_at": _OBSERVED_AT,
        "available_at": _AVAILABLE_AT,
        "source_dataset_id": "TEST_ONLY_SYNTHETIC_FX_DATASET",
        "source_dataset_version": "test-only-v1",
        "source_record_id": "fx:test-only:1",
        "source_checksum": None,
        "ingestion_provenance": "TEST_ONLY: manual synthetic fixture, not a real ingestion run",
        "quality_status": FxObservationQualityStatus.UNVALIDATED,
    }


def test_observation_has_no_default_rate() -> None:
    content = _complete_observation_content()
    del content["rate"]
    with pytest.raises(ValidationError, match="rate"):
        FxObservationReference.model_validate(
            {"fx_observation_id": "sha256:" + "0" * 64, **content}
        )


def test_observation_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _observation(unexpected_field="not allowed")


def test_observation_rejects_forged_identity() -> None:
    with pytest.raises(ValidationError, match="identity does not match content"):
        FxObservationReference.model_validate(
            {"fx_observation_id": "sha256:" + "0" * 64, **_complete_observation_content()}
        )


def test_observation_identity_is_stable_for_identical_content() -> None:
    first = _observation()
    second = _observation()
    assert first.fx_observation_id == second.fx_observation_id


def test_observation_identity_is_equivalent_decimal_scale_invariant() -> None:
    first = _observation(rate="1.08")
    second = _observation(rate="1.0800")
    assert first.fx_observation_id == second.fx_observation_id


def test_observation_identity_changes_with_rate() -> None:
    first = _observation(rate="1.08")
    second = _observation(rate="1.09")
    assert first.fx_observation_id != second.fx_observation_id


def test_observation_identity_changes_with_provider() -> None:
    first = _observation()
    second = _observation(provider="TEST_ONLY_OTHER_PROVIDER")
    assert first.fx_observation_id != second.fx_observation_id


# --- Provenance and quality (Finding 2) -------------------------------------


def test_observation_requires_source_record_id_or_checksum() -> None:
    with pytest.raises(ValidationError, match="source_record_id or source_checksum"):
        _observation(source_record_id=None, source_checksum=None)


def test_observation_accepts_checksum_without_record_id() -> None:
    observation = _observation(source_record_id=None, source_checksum="sha256:" + "a" * 64)
    assert observation.source_record_id is None
    assert observation.source_checksum == "sha256:" + "a" * 64


def test_observation_accepts_record_id_without_checksum() -> None:
    observation = _observation(source_record_id="fx:test-only:1", source_checksum=None)
    assert observation.source_record_id == "fx:test-only:1"
    assert observation.source_checksum is None


def test_observation_accepts_record_id_with_checksum() -> None:
    observation = _observation(
        source_record_id="fx:test-only:1", source_checksum="sha256:" + "a" * 64
    )
    assert observation.source_record_id == "fx:test-only:1"
    assert observation.source_checksum == "sha256:" + "a" * 64


def test_observation_rejects_whitespace_only_record_id_with_no_checksum() -> None:
    with pytest.raises(ValidationError, match="source_record_id must be nonblank"):
        _observation(source_record_id="   ", source_checksum=None)


@pytest.mark.parametrize("blank_record_id", ["", "   ", "\t\n "])
def test_observation_rejects_blank_record_id_even_with_valid_checksum(
    blank_record_id: str,
) -> None:
    """The bug this fix closes: a blank source_record_id must be rejected outright,
    not silently accepted because a valid source_checksum is also present."""
    with pytest.raises(ValidationError, match="source_record_id must be nonblank"):
        _observation(source_record_id=blank_record_id, source_checksum="sha256:" + "a" * 64)


def test_observation_identity_unchanged_for_already_valid_record_id() -> None:
    """This fix only rejects previously-invalid (blank) input; it must not change
    the computed identity for input that was already valid."""
    content = _complete_observation_content()
    expected_id = calculate_fx_observation_id(content)
    observation = _observation()
    assert observation.fx_observation_id == expected_id


def test_observation_rejects_empty_checksum() -> None:
    with pytest.raises(ValidationError, match="source_checksum must be nonblank"):
        _observation(source_record_id=None, source_checksum="")


def test_observation_rejects_whitespace_only_checksum() -> None:
    with pytest.raises(ValidationError, match="source_checksum must be nonblank"):
        _observation(source_record_id=None, source_checksum="   ")


def test_observation_has_no_default_provenance_or_quality_fields() -> None:
    for missing_field in (
        "source_dataset_id",
        "source_dataset_version",
        "ingestion_provenance",
        "quality_status",
    ):
        content = _complete_observation_content()
        del content[missing_field]
        with pytest.raises(ValidationError, match=missing_field):
            FxObservationReference.model_validate(
                {"fx_observation_id": "sha256:" + "0" * 64, **content}
            )


def test_observation_identity_changes_with_source_dataset_id() -> None:
    first = _observation()
    second = _observation(source_dataset_id="TEST_ONLY_OTHER_DATASET")
    assert first.fx_observation_id != second.fx_observation_id


def test_observation_identity_changes_with_source_dataset_version() -> None:
    first = _observation()
    second = _observation(source_dataset_version="test-only-v2")
    assert first.fx_observation_id != second.fx_observation_id


def test_observation_identity_changes_with_source_checksum() -> None:
    first = _observation(source_checksum=None)
    second = _observation(source_checksum="sha256:" + "b" * 64)
    assert first.fx_observation_id != second.fx_observation_id


def test_observation_identity_changes_with_ingestion_provenance() -> None:
    first = _observation()
    second = _observation(ingestion_provenance="TEST_ONLY: a different synthetic fixture run")
    assert first.fx_observation_id != second.fx_observation_id


def test_observation_identity_changes_with_quality_status() -> None:
    first = _observation(quality_status=FxObservationQualityStatus.UNVALIDATED)
    second = _observation(quality_status=FxObservationQualityStatus.SUSPECT)
    assert first.fx_observation_id != second.fx_observation_id


@pytest.mark.parametrize(
    "blank_field",
    [
        "provider",
        "methodology_version",
        "source_dataset_id",
        "source_dataset_version",
        "ingestion_provenance",
    ],
)
def test_observation_rejects_empty_required_provenance_field(blank_field: str) -> None:
    # An empty string is caught by the field's own min_length=1 constraint
    # (pydantic's built-in "at least 1 character" message); whitespace-only
    # values reach the custom nonblank check below instead.
    with pytest.raises(ValidationError, match="at least 1 character|nonblank"):
        _observation(**{blank_field: ""})


@pytest.mark.parametrize(
    "blank_field",
    [
        "provider",
        "methodology_version",
        "source_dataset_id",
        "source_dataset_version",
        "ingestion_provenance",
    ],
)
def test_observation_rejects_whitespace_only_required_provenance_field(blank_field: str) -> None:
    with pytest.raises(ValidationError, match="nonblank"):
        _observation(**{blank_field: "   \t  "})


@pytest.mark.parametrize(
    "malformed_checksum",
    [
        "not-a-checksum",
        "sha256:" + "a" * 63,  # too short
        "sha256:" + "a" * 65,  # too long
        "sha256:" + "A" * 64,  # uppercase hex not accepted
        "sha256:" + "g" * 64,  # non-hex characters
        "md5:" + "a" * 32,  # wrong algorithm prefix
        "a" * 64,  # missing 'sha256:' prefix entirely
    ],
)
def test_observation_rejects_malformed_checksum(malformed_checksum: str) -> None:
    with pytest.raises(ValidationError, match="source_checksum must match"):
        _observation(source_checksum=malformed_checksum)


def test_observation_rejects_malformed_checksum_as_sole_locator() -> None:
    """A malformed checksum is rejected even when it is the only supplied locator,
    not only when a valid source_record_id is also present."""
    with pytest.raises(ValidationError, match="source_checksum must match"):
        _observation(source_record_id=None, source_checksum="not-a-real-checksum")


def test_observation_accepts_valid_checksum_as_sole_locator() -> None:
    observation = _observation(source_record_id=None, source_checksum="sha256:" + "c" * 64)
    assert observation.source_checksum == "sha256:" + "c" * 64


def test_observation_accepts_valid_provenance_with_both_locators() -> None:
    observation = _observation(
        source_record_id="fx:test-only:1", source_checksum="sha256:" + "d" * 64
    )
    assert observation.source_record_id == "fx:test-only:1"
    assert observation.source_checksum == "sha256:" + "d" * 64


# --- Decimal-only public identity boundary (Finding 3) ----------------------


def test_calculate_fx_observation_id_rejects_float_rate_directly() -> None:
    content = _complete_observation_content()
    content["rate"] = 1.08
    with pytest.raises(ValueError, match="float"):
        calculate_fx_observation_id(content)


def test_calculate_fx_observation_id_rejects_non_finite_rate_directly() -> None:
    for bad_rate in ("NaN", "Infinity", "-Infinity"):
        content = _complete_observation_content()
        content["rate"] = bad_rate
        with pytest.raises(ValueError, match="finite"):
            calculate_fx_observation_id(content)


def test_calculate_fx_observation_id_rejects_malformed_rate_directly() -> None:
    content = _complete_observation_content()
    content["rate"] = "not-a-decimal"
    with pytest.raises(ValueError, match="valid Decimal"):
        calculate_fx_observation_id(content)


def test_calculate_fx_observation_id_accepts_decimal_and_string_rate_directly() -> None:
    content = _complete_observation_content()
    content["rate"] = "1.08"
    assert calculate_fx_observation_id(content) == calculate_fx_observation_id(
        {**content, "rate": Decimal("1.08")}
    )


# --- FxConversionPolicyConfiguration ----------------------------------------


def test_policy_requires_two_distinct_currencies() -> None:
    with pytest.raises(ValidationError, match="two distinct currencies"):
        _policy(base_currency="EUR", trading_currency="EUR")


def test_policy_has_no_default_staleness_threshold() -> None:
    content: dict[str, object] = {
        "schema_version": "fx-conversion-policy-v1",
        "policy_name": "INITIAL_CONVERSION_AND_REPORTING_MARK_V1",
        "model_version": "test-only-v1",
        "base_currency": "EUR",
        "trading_currency": "USD",
        "quote_convention": FxQuoteConvention.DECLARED_REFERENCE,
        "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
    }
    with pytest.raises(ValidationError, match="maximum_observation_staleness_seconds"):
        FxConversionPolicyConfiguration.model_validate(
            {"fx_conversion_policy_id": "sha256:" + "0" * 64, **content}
        )


def test_policy_rejects_non_positive_staleness_threshold() -> None:
    with pytest.raises(ValidationError):
        _policy(maximum_observation_staleness_seconds=0)
    with pytest.raises(ValidationError):
        _policy(maximum_observation_staleness_seconds=-1)


def test_policy_requires_explicit_quote_convention() -> None:
    content: dict[str, object] = {
        "schema_version": "fx-conversion-policy-v1",
        "policy_name": "INITIAL_CONVERSION_AND_REPORTING_MARK_V1",
        "model_version": "test-only-v1",
        "base_currency": "EUR",
        "trading_currency": "USD",
        "maximum_observation_staleness_seconds": 60,
        "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
    }
    with pytest.raises(ValidationError, match="quote_convention"):
        FxConversionPolicyConfiguration.model_validate(
            {"fx_conversion_policy_id": "sha256:" + "0" * 64, **content}
        )


def test_policy_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _policy(unexpected_field="not allowed")


def test_policy_rejects_forged_identity() -> None:
    with pytest.raises(ValidationError, match="identity does not match content"):
        FxConversionPolicyConfiguration.model_validate(
            {
                "fx_conversion_policy_id": "sha256:" + "0" * 64,
                "schema_version": "fx-conversion-policy-v1",
                "policy_name": "INITIAL_CONVERSION_AND_REPORTING_MARK_V1",
                "model_version": "test-only-v1",
                "base_currency": "EUR",
                "trading_currency": "USD",
                "quote_convention": FxQuoteConvention.DECLARED_REFERENCE,
                "maximum_observation_staleness_seconds": 60,
                "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
            }
        )


def test_policy_identity_is_stable_for_identical_content() -> None:
    first = _policy()
    second = _policy()
    assert first.fx_conversion_policy_id == second.fx_conversion_policy_id


def test_policy_identity_changes_with_quote_convention() -> None:
    first = _policy(quote_convention=FxQuoteConvention.DECLARED_REFERENCE)
    second = _policy(quote_convention=FxQuoteConvention.MID)
    assert first.fx_conversion_policy_id != second.fx_conversion_policy_id


def test_policy_identity_changes_with_staleness_threshold() -> None:
    first = _policy(maximum_observation_staleness_seconds=60)
    second = _policy(maximum_observation_staleness_seconds=120)
    assert first.fx_conversion_policy_id != second.fx_conversion_policy_id


def test_policy_identity_changes_with_rounding_policy() -> None:
    first = _policy(rounding_policy=CostRoundingPolicy.ROUND_HALF_EVEN_V1)
    assert first.rounding_policy is CostRoundingPolicy.ROUND_HALF_EVEN_V1
    assert set(CostRoundingPolicy) == {CostRoundingPolicy.ROUND_HALF_EVEN_V1}


# --- Explicit scope boundary for this milestone -----------------------------


def test_fx_module_implements_no_conversion_execution_or_posting_symbols() -> None:
    """Pure causal and quote-side-aware selection exist; actual conversion
    arithmetic, balanced-leg construction, posting and manifest binding do
    not."""
    forbidden_names = {
        "resolve_fx_conversion",
        "compute_fx_conversion",
        "FxConversionLegPair",
        "post_fx_conversion",
        "apply_fx_conversion",
        "bind_fx_conversion_policy_to_manifest",
    }
    exported = set(dir(fx_module))
    assert forbidden_names.isdisjoint(exported)
    assert "select_eligible_fx_observation" in exported
    assert "select_eligible_fx_observation_for_conversion" in exported
    assert "select_eligible_fx_observation_for_valuation" in exported
    assert "calculate_fx_source_checksum" in exported


# --- select_eligible_fx_observation (pure causal selection) -----------------

_T = datetime(2026, 1, 2, 15, 0, 0, tzinfo=UTC)


def _selection_policy(**changes: object) -> FxConversionPolicyConfiguration:
    changes.setdefault("maximum_observation_staleness_seconds", 60)
    return _policy(**changes)


def _eligible_observation(**changes: object) -> FxObservationReference:
    """A baseline observation that is fully eligible relative to _T under
    _selection_policy()'s default 60-second staleness threshold."""
    defaults: dict[str, object] = {
        "observed_at": _T - timedelta(seconds=30),
        "available_at": _T - timedelta(seconds=10),
        "quality_status": FxObservationQualityStatus.VALIDATED,
    }
    defaults.update(changes)
    return _observation(**defaults)


def test_selection_excludes_future_availability() -> None:
    policy = _selection_policy()
    observation = _eligible_observation(available_at=_T + timedelta(seconds=1))
    result = select_eligible_fx_observation([observation], policy, _T)
    assert isinstance(result, FxObservationUnavailable)
    assert result.reason is FxObservationUnavailableReason.NO_ELIGIBLE_OBSERVATION


def test_selection_accepts_availability_exactly_at_evaluated_at() -> None:
    policy = _selection_policy()
    observation = _eligible_observation(available_at=_T)
    result = select_eligible_fx_observation([observation], policy, _T)
    assert result == observation


def test_selection_rejects_observation_that_was_already_stale_when_available() -> None:
    """An observation observed long ago but only just published must still be
    rejected: staleness is measured from observed_at, not available_at. Under
    the old (available_at-based) definition this would wrongly show zero
    staleness and be accepted."""
    policy = _selection_policy(maximum_observation_staleness_seconds=60)
    observation = _eligible_observation(
        observed_at=_T - timedelta(seconds=1000),
        available_at=_T,
    )
    result = select_eligible_fx_observation([observation], policy, _T)
    assert isinstance(result, FxObservationUnavailable)
    assert result.reason is FxObservationUnavailableReason.NO_ELIGIBLE_OBSERVATION


def test_selection_accepts_observation_exactly_at_staleness_boundary() -> None:
    policy = _selection_policy(maximum_observation_staleness_seconds=60)
    observation = _eligible_observation(
        observed_at=_T - timedelta(seconds=60), available_at=_T - timedelta(seconds=1)
    )
    result = select_eligible_fx_observation([observation], policy, _T)
    assert result == observation


def test_selection_rejects_observation_one_second_beyond_staleness_boundary() -> None:
    policy = _selection_policy(maximum_observation_staleness_seconds=60)
    observation = _eligible_observation(
        observed_at=_T - timedelta(seconds=61), available_at=_T - timedelta(seconds=1)
    )
    result = select_eligible_fx_observation([observation], policy, _T)
    assert isinstance(result, FxObservationUnavailable)


@pytest.mark.parametrize(
    "quality_status",
    [FxObservationQualityStatus.UNVALIDATED, FxObservationQualityStatus.SUSPECT],
)
def test_selection_rejects_non_validated_quality(
    quality_status: FxObservationQualityStatus,
) -> None:
    policy = _selection_policy()
    observation = _eligible_observation(quality_status=quality_status)
    result = select_eligible_fx_observation([observation], policy, _T)
    assert isinstance(result, FxObservationUnavailable)


def test_selection_accepts_validated_quality() -> None:
    policy = _selection_policy()
    observation = _eligible_observation(quality_status=FxObservationQualityStatus.VALIDATED)
    result = select_eligible_fx_observation([observation], policy, _T)
    assert result == observation


def test_selection_rejects_currency_pair_mismatch() -> None:
    policy = _selection_policy(base_currency="EUR", trading_currency="USD")
    observation = _eligible_observation(base_currency="GBP", quote_currency="USD")
    result = select_eligible_fx_observation([observation], policy, _T)
    assert isinstance(result, FxObservationUnavailable)


def test_selection_prefers_latest_observed_at() -> None:
    policy = _selection_policy()
    older = _eligible_observation(
        observed_at=_T - timedelta(seconds=40), source_record_id="fx:older"
    )
    newer = _eligible_observation(
        observed_at=_T - timedelta(seconds=10), source_record_id="fx:newer"
    )
    result = select_eligible_fx_observation([older, newer], policy, _T)
    assert result == newer


def test_selection_tie_breaks_by_available_at_when_observed_at_matches() -> None:
    policy = _selection_policy()
    same_time = _T - timedelta(seconds=30)
    earlier_available = _eligible_observation(
        observed_at=same_time, available_at=_T - timedelta(seconds=20), source_record_id="fx:a"
    )
    later_available = _eligible_observation(
        observed_at=same_time, available_at=_T - timedelta(seconds=5), source_record_id="fx:b"
    )
    result = select_eligible_fx_observation([earlier_available, later_available], policy, _T)
    assert result == later_available


def test_selection_tie_breaks_by_observation_id_when_times_match() -> None:
    policy = _selection_policy()
    same_time = _T - timedelta(seconds=30)
    same_available = _T - timedelta(seconds=10)
    first = _eligible_observation(
        observed_at=same_time, available_at=same_available, source_record_id="fx:aaa"
    )
    second = _eligible_observation(
        observed_at=same_time, available_at=same_available, source_record_id="fx:zzz"
    )
    assert first.fx_observation_id != second.fx_observation_id
    expected = max([first, second], key=lambda o: str(o.fx_observation_id))
    result = select_eligible_fx_observation([first, second], policy, _T)
    assert result == expected


def test_selection_empty_prefix_fails_closed() -> None:
    policy = _selection_policy()
    result = select_eligible_fx_observation([], policy, _T)
    assert isinstance(result, FxObservationUnavailable)
    assert result.reason is FxObservationUnavailableReason.NO_ELIGIBLE_OBSERVATION
    assert result.evaluated_at == _T
    assert result.fx_conversion_policy_id == policy.fx_conversion_policy_id


def test_selection_filters_ineligible_candidates_from_mixed_prefix() -> None:
    policy = _selection_policy()
    future = _eligible_observation(
        available_at=_T + timedelta(seconds=1), source_record_id="fx:future"
    )
    stale = _eligible_observation(
        observed_at=_T - timedelta(seconds=1000), source_record_id="fx:stale"
    )
    suspect = _eligible_observation(
        quality_status=FxObservationQualityStatus.SUSPECT, source_record_id="fx:suspect"
    )
    wrong_pair = _eligible_observation(
        base_currency="GBP", quote_currency="USD", source_record_id="fx:wrongpair"
    )
    eligible = _eligible_observation(
        observed_at=_T - timedelta(seconds=5),
        available_at=_T - timedelta(seconds=3),
        source_record_id="fx:eligible",
    )
    result = select_eligible_fx_observation(
        [future, stale, suspect, wrong_pair, eligible], policy, _T
    )
    assert result == eligible


def test_selection_ignores_quote_convention_mismatch() -> None:
    """This slice does not implement quote-side selection; an observation whose
    quote_convention differs from the policy's remains eligible on causal
    grounds alone."""
    policy = _selection_policy(quote_convention=FxQuoteConvention.DECLARED_REFERENCE)
    observation = _eligible_observation(quote_convention=FxQuoteConvention.BID)
    result = select_eligible_fx_observation([observation], policy, _T)
    assert result == observation


def test_selection_rejects_naive_evaluated_at() -> None:
    policy = _selection_policy()
    observation = _eligible_observation()
    with pytest.raises(ValueError, match="timezone-aware"):
        select_eligible_fx_observation([observation], policy, datetime(2026, 1, 2, 15, 0, 0))


# --- calculate_fx_source_checksum -------------------------------------------


def _checksum(
    *,
    base_currency: str = "EUR",
    quote_currency: str = "USD",
    provider: str = "TEST_ONLY_SYNTHETIC_PROVIDER",
    quote_convention: FxQuoteConvention = FxQuoteConvention.BID,
    rate: Decimal | str = "1.08",
    observed_at: datetime = _OBSERVED_AT,
) -> str:
    return calculate_fx_source_checksum(
        base_currency=base_currency,
        quote_currency=quote_currency,
        provider=provider,
        quote_convention=quote_convention,
        rate=rate,
        observed_at=observed_at,
    )


def test_fx_source_checksum_is_stable_for_identical_content() -> None:
    assert _checksum() == _checksum()


def test_fx_source_checksum_matches_expected_format() -> None:
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", _checksum())


def test_fx_source_checksum_is_decimal_scale_invariant() -> None:
    assert _checksum(rate="1.08") == _checksum(rate="1.0800")


def test_fx_source_checksum_accepts_decimal_and_string_rate_identically() -> None:
    assert _checksum(rate="1.08") == _checksum(rate=Decimal("1.08"))


def test_fx_source_checksum_changes_with_rate() -> None:
    assert _checksum(rate="1.08") != _checksum(rate="1.09")


def test_fx_source_checksum_changes_with_quote_convention() -> None:
    assert _checksum(quote_convention=FxQuoteConvention.BID) != _checksum(
        quote_convention=FxQuoteConvention.ASK
    )


def test_fx_source_checksum_changes_with_provider() -> None:
    assert _checksum(provider="TEST_ONLY_A") != _checksum(provider="TEST_ONLY_B")


def test_fx_source_checksum_changes_with_observed_at() -> None:
    assert _checksum(observed_at=_OBSERVED_AT) != _checksum(
        observed_at=_OBSERVED_AT + timedelta(seconds=1)
    )


def test_fx_source_checksum_changes_with_currency_pair() -> None:
    assert _checksum(base_currency="EUR") != _checksum(base_currency="GBP")


def test_fx_source_checksum_has_no_available_at_parameter() -> None:
    """available_at is our ingestion timing, not the provider's fact; the
    function does not even accept it, proving the fact/handling boundary
    structurally rather than only by convention."""
    assert "available_at" not in inspect.signature(calculate_fx_source_checksum).parameters


def test_fx_source_checksum_rejects_float_rate() -> None:
    with pytest.raises(ValueError, match="float"):
        _checksum(rate=1.08)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_rate", ["NaN", "Infinity", "-Infinity"])
def test_fx_source_checksum_rejects_non_finite_rate(bad_rate: str) -> None:
    with pytest.raises(ValueError, match="finite"):
        _checksum(rate=bad_rate)


def test_fx_source_checksum_rejects_naive_observed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _checksum(observed_at=datetime(2026, 1, 2, 14, 30))


# --- FxValuationPolicyConfiguration ------------------------------------------


def _valuation_policy(**changes: object) -> FxValuationPolicyConfiguration:
    content: dict[str, object] = {
        "schema_version": "fx-valuation-policy-v1",
        "policy_name": "TEST_ONLY_VALUATION_POLICY",
        "model_version": "test-only-v1",
        "base_currency": "EUR",
        "trading_currency": "USD",
        "quote_convention": FxQuoteConvention.MID,
        "maximum_observation_staleness_seconds": 60,
        "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
    }
    content.update(changes)
    return FxValuationPolicyConfiguration.model_validate(
        {"fx_valuation_policy_id": calculate_fx_valuation_policy_id(content), **content}
    )


def test_valuation_policy_accepts_mid() -> None:
    policy = _valuation_policy(quote_convention=FxQuoteConvention.MID)
    assert policy.quote_convention is FxQuoteConvention.MID


def test_valuation_policy_accepts_declared_reference() -> None:
    policy = _valuation_policy(quote_convention=FxQuoteConvention.DECLARED_REFERENCE)
    assert policy.quote_convention is FxQuoteConvention.DECLARED_REFERENCE


@pytest.mark.parametrize("transactional_side", [FxQuoteConvention.BID, FxQuoteConvention.ASK])
def test_valuation_policy_rejects_transactional_quote_side(
    transactional_side: FxQuoteConvention,
) -> None:
    with pytest.raises(ValidationError, match="MID or DECLARED_REFERENCE"):
        _valuation_policy(quote_convention=transactional_side)


def test_valuation_policy_requires_two_distinct_currencies() -> None:
    with pytest.raises(ValidationError, match="two distinct currencies"):
        _valuation_policy(base_currency="EUR", trading_currency="EUR")


def test_valuation_policy_has_no_default_staleness_threshold() -> None:
    content: dict[str, object] = {
        "schema_version": "fx-valuation-policy-v1",
        "policy_name": "TEST_ONLY_VALUATION_POLICY",
        "model_version": "test-only-v1",
        "base_currency": "EUR",
        "trading_currency": "USD",
        "quote_convention": FxQuoteConvention.MID,
        "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
    }
    with pytest.raises(ValidationError, match="maximum_observation_staleness_seconds"):
        FxValuationPolicyConfiguration.model_validate(
            {"fx_valuation_policy_id": "sha256:" + "0" * 64, **content}
        )


def test_valuation_policy_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _valuation_policy(unexpected_field="not allowed")


def test_valuation_policy_rejects_forged_identity() -> None:
    content: dict[str, object] = {
        "schema_version": "fx-valuation-policy-v1",
        "policy_name": "TEST_ONLY_VALUATION_POLICY",
        "model_version": "test-only-v1",
        "base_currency": "EUR",
        "trading_currency": "USD",
        "quote_convention": FxQuoteConvention.MID,
        "maximum_observation_staleness_seconds": 60,
        "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
    }
    with pytest.raises(ValidationError, match="identity does not match content"):
        FxValuationPolicyConfiguration.model_validate(
            {"fx_valuation_policy_id": "sha256:" + "0" * 64, **content}
        )


def test_valuation_policy_identity_is_stable_for_identical_content() -> None:
    first = _valuation_policy()
    second = _valuation_policy()
    assert first.fx_valuation_policy_id == second.fx_valuation_policy_id


def test_valuation_policy_identity_changes_with_quote_convention() -> None:
    first = _valuation_policy(quote_convention=FxQuoteConvention.MID)
    second = _valuation_policy(quote_convention=FxQuoteConvention.DECLARED_REFERENCE)
    assert first.fx_valuation_policy_id != second.fx_valuation_policy_id


def test_valuation_policy_identity_domain_is_distinct_from_conversion_policy() -> None:
    """Conversion and valuation policies use different identity types and schema
    versions; they never share an identity space even with similar fields."""
    conversion = _policy(quote_convention=FxQuoteConvention.MID)
    valuation = _valuation_policy(quote_convention=FxQuoteConvention.MID)
    assert isinstance(conversion.fx_conversion_policy_id, FxConversionPolicyId)
    assert isinstance(valuation.fx_valuation_policy_id, FxValuationPolicyId)
    assert str(conversion.fx_conversion_policy_id) != str(valuation.fx_valuation_policy_id)


# --- Quote-side-aware selection: conversion ---------------------------------


def _conversion_selection_policy(**changes: object) -> FxConversionPolicyConfiguration:
    """A qualifying policy for select_eligible_fx_observation_for_conversion:
    V2, the one approved direction, and BID by default. select_conversion_v1_*
    tests below construct V1 explicitly instead, to prove it's rejected."""
    changes.setdefault("quote_convention", FxQuoteConvention.BID)
    changes.setdefault("schema_version", "fx-conversion-policy-v2")
    changes.setdefault("conversion_direction", FxConversionDirection.SELL_BASE_FOR_TRADING)
    return _selection_policy(**changes)


def test_conversion_selection_rejects_v1_eur_usd_ask_bypass() -> None:
    """Reproduces Codex's exact confirmed finding: an fx-conversion-policy-v1
    EUR/USD policy declaring ASK must no longer let a caller select an ASK
    observation through select_eligible_fx_observation_for_conversion. It
    must be rejected outright, not silently accepted and not returned as
    FxConversionQuoteUnavailable (that would mislabel an invalid policy as
    missing FX data)."""
    v1_ask_policy = _policy(
        base_currency="EUR",
        trading_currency="USD",
        quote_convention=FxQuoteConvention.ASK,
    )
    assert v1_ask_policy.schema_version == "fx-conversion-policy-v1"
    ask_observation = _eligible_observation(quote_convention=FxQuoteConvention.ASK)
    with pytest.raises(FxConversionPolicyUnsupportedError, match="fx-conversion-policy-v2"):
        select_eligible_fx_observation_for_conversion([ask_observation], v1_ask_policy, _T)


def test_conversion_selection_rejects_v1_even_with_coincidentally_correct_bid() -> None:
    """A V1 policy carries no structural guarantee, so it is rejected even
    when its quote_convention already happens to be BID -- accepting it
    would still let a caller bypass the enforced V2 rule via an
    unenforced, independently mutable V1 instance."""
    v1_bid_policy = _policy(
        base_currency="EUR",
        trading_currency="USD",
        quote_convention=FxQuoteConvention.BID,
    )
    bid_observation = _eligible_observation(quote_convention=FxQuoteConvention.BID)
    with pytest.raises(FxConversionPolicyUnsupportedError):
        select_eligible_fx_observation_for_conversion([bid_observation], v1_bid_policy, _T)


def test_conversion_selection_rejection_is_not_typed_unavailable_evidence() -> None:
    """The V1 rejection is a raised exception, never a returned
    FxConversionQuoteUnavailable -- confirming an invalid policy is never
    mislabeled as a data-availability outcome."""
    v1_policy = _policy(base_currency="EUR", trading_currency="USD")
    try:
        select_eligible_fx_observation_for_conversion([], v1_policy, _T)
    except FxConversionPolicyUnsupportedError as exc:
        assert not isinstance(exc, FxConversionQuoteUnavailable)
    else:
        pytest.fail("expected FxConversionPolicyUnsupportedError to be raised")


def test_conversion_selection_accepts_matching_quote_side() -> None:
    policy = _conversion_selection_policy(quote_convention=FxQuoteConvention.BID)
    observation = _eligible_observation(quote_convention=FxQuoteConvention.BID)
    result = select_eligible_fx_observation_for_conversion([observation], policy, _T)
    assert result == observation


def test_conversion_selection_rejects_mismatched_quote_side() -> None:
    policy = _conversion_selection_policy(quote_convention=FxQuoteConvention.BID)
    observation = _eligible_observation(quote_convention=FxQuoteConvention.ASK)
    result = select_eligible_fx_observation_for_conversion([observation], policy, _T)
    assert isinstance(result, FxConversionQuoteUnavailable)
    assert result.reason is FxQuoteUnavailableReason.REQUIRED_QUOTE_SIDE_UNAVAILABLE


def test_conversion_selection_never_falls_back_to_a_different_side() -> None:
    """No-silent-fallback proof: an ASK observation is otherwise perfectly
    causally eligible, but a BID-requiring policy must still fail closed
    rather than substituting it."""
    policy = _conversion_selection_policy(quote_convention=FxQuoteConvention.BID)
    ask_only = _eligible_observation(quote_convention=FxQuoteConvention.ASK)
    result = select_eligible_fx_observation_for_conversion([ask_only], policy, _T)
    assert isinstance(result, FxConversionQuoteUnavailable)


def test_conversion_selection_distinguishes_no_eligible_from_wrong_side() -> None:
    policy = _conversion_selection_policy(quote_convention=FxQuoteConvention.BID)
    future = _eligible_observation(
        available_at=_T + timedelta(seconds=1), quote_convention=FxQuoteConvention.BID
    )
    no_eligible = select_eligible_fx_observation_for_conversion([future], policy, _T)
    assert isinstance(no_eligible, FxConversionQuoteUnavailable)
    assert no_eligible.reason is FxQuoteUnavailableReason.NO_ELIGIBLE_OBSERVATION

    wrong_side = _eligible_observation(quote_convention=FxQuoteConvention.MID)
    side_unavailable = select_eligible_fx_observation_for_conversion([wrong_side], policy, _T)
    assert isinstance(side_unavailable, FxConversionQuoteUnavailable)
    assert side_unavailable.reason is FxQuoteUnavailableReason.REQUIRED_QUOTE_SIDE_UNAVAILABLE


def test_conversion_selection_prefers_freshest_matching_side_among_mixed_candidates() -> None:
    policy = _conversion_selection_policy(quote_convention=FxQuoteConvention.BID)
    older_match = _eligible_observation(
        quote_convention=FxQuoteConvention.BID,
        observed_at=_T - timedelta(seconds=40),
        source_record_id="fx:older-match",
    )
    newer_match = _eligible_observation(
        quote_convention=FxQuoteConvention.BID,
        observed_at=_T - timedelta(seconds=10),
        source_record_id="fx:newer-match",
    )
    fresher_wrong_side = _eligible_observation(
        quote_convention=FxQuoteConvention.ASK,
        observed_at=_T - timedelta(seconds=1),
        available_at=_T,
        source_record_id="fx:fresher-wrong-side",
    )
    result = select_eligible_fx_observation_for_conversion(
        [older_match, newer_match, fresher_wrong_side], policy, _T
    )
    assert result == newer_match


def test_conversion_selection_deterministic_tie_break_among_matching_side() -> None:
    policy = _conversion_selection_policy(quote_convention=FxQuoteConvention.BID)
    same_time = _T - timedelta(seconds=30)
    same_available = _T - timedelta(seconds=10)
    first = _eligible_observation(
        quote_convention=FxQuoteConvention.BID,
        observed_at=same_time,
        available_at=same_available,
        source_record_id="fx:aaa",
    )
    second = _eligible_observation(
        quote_convention=FxQuoteConvention.BID,
        observed_at=same_time,
        available_at=same_available,
        source_record_id="fx:zzz",
    )
    assert first.fx_observation_id != second.fx_observation_id
    expected = max([first, second], key=lambda o: str(o.fx_observation_id))
    result = select_eligible_fx_observation_for_conversion([first, second], policy, _T)
    assert result == expected


def test_conversion_selection_empty_prefix_fails_closed() -> None:
    policy = _conversion_selection_policy()
    result = select_eligible_fx_observation_for_conversion([], policy, _T)
    assert isinstance(result, FxConversionQuoteUnavailable)
    assert result.reason is FxQuoteUnavailableReason.NO_ELIGIBLE_OBSERVATION
    assert result.evaluated_at == _T
    assert result.fx_conversion_policy_id == policy.fx_conversion_policy_id


# --- Quote-side-aware selection: valuation ----------------------------------


def _valuation_selection_policy(**changes: object) -> FxValuationPolicyConfiguration:
    changes.setdefault("maximum_observation_staleness_seconds", 60)
    changes.setdefault("quote_convention", FxQuoteConvention.MID)
    return _valuation_policy(**changes)


def test_valuation_selection_accepts_matching_mid() -> None:
    policy = _valuation_selection_policy(quote_convention=FxQuoteConvention.MID)
    observation = _eligible_observation(quote_convention=FxQuoteConvention.MID)
    result = select_eligible_fx_observation_for_valuation([observation], policy, _T)
    assert result == observation


def test_valuation_selection_rejects_mismatched_quote_side() -> None:
    policy = _valuation_selection_policy(quote_convention=FxQuoteConvention.MID)
    observation = _eligible_observation(quote_convention=FxQuoteConvention.DECLARED_REFERENCE)
    result = select_eligible_fx_observation_for_valuation([observation], policy, _T)
    assert isinstance(result, FxValuationQuoteUnavailable)
    assert result.reason is FxQuoteUnavailableReason.REQUIRED_QUOTE_SIDE_UNAVAILABLE


def test_valuation_selection_never_falls_back_to_a_transactional_side() -> None:
    """No-silent-fallback proof for valuation: a BID observation is otherwise
    perfectly causally eligible, but a MID-requiring valuation policy must
    still fail closed as incomplete reporting rather than substituting it."""
    policy = _valuation_selection_policy(quote_convention=FxQuoteConvention.MID)
    bid_only = _eligible_observation(quote_convention=FxQuoteConvention.BID)
    result = select_eligible_fx_observation_for_valuation([bid_only], policy, _T)
    assert isinstance(result, FxValuationQuoteUnavailable)


def test_valuation_selection_empty_prefix_fails_closed_as_incomplete_reporting() -> None:
    policy = _valuation_selection_policy()
    result = select_eligible_fx_observation_for_valuation([], policy, _T)
    assert isinstance(result, FxValuationQuoteUnavailable)
    assert result.reason is FxQuoteUnavailableReason.NO_ELIGIBLE_OBSERVATION
    assert result.evaluated_at == _T
    assert result.fx_valuation_policy_id == policy.fx_valuation_policy_id


def test_valuation_selection_deterministic_tie_break_among_matching_side() -> None:
    policy = _valuation_selection_policy(quote_convention=FxQuoteConvention.MID)
    same_time = _T - timedelta(seconds=30)
    same_available = _T - timedelta(seconds=10)
    first = _eligible_observation(
        quote_convention=FxQuoteConvention.MID,
        observed_at=same_time,
        available_at=same_available,
        source_record_id="fx:mmm",
    )
    second = _eligible_observation(
        quote_convention=FxQuoteConvention.MID,
        observed_at=same_time,
        available_at=same_available,
        source_record_id="fx:nnn",
    )
    assert first.fx_observation_id != second.fx_observation_id
    expected = max([first, second], key=lambda o: str(o.fx_observation_id))
    result = select_eligible_fx_observation_for_valuation([first, second], policy, _T)
    assert result == expected


# --- Identity/contract compatibility with already-committed code -----------


def test_existing_conversion_policy_contract_gained_only_the_v2_direction_field() -> None:
    """FxConversionPolicyConfiguration's shape grew by exactly one additive,
    optional field (conversion_direction) for V2 support; V1 identity
    behavior itself is proven unchanged by the literal hash pin above, not
    by this field-set check."""
    assert set(FxConversionPolicyConfiguration.model_fields) == {
        "fx_conversion_policy_id",
        "schema_version",
        "policy_name",
        "model_version",
        "base_currency",
        "trading_currency",
        "quote_convention",
        "maximum_observation_staleness_seconds",
        "rounding_policy",
        "conversion_direction",
    }
    policy = _policy()
    assert policy.conversion_direction is None
    assert policy.fx_conversion_policy_id == calculate_fx_conversion_policy_id(policy)


def test_v1_conversion_policy_identity_is_pinned_to_pre_v2_hash() -> None:
    """Literal identity pin, independently computed with the pre-V2
    implementation (uv run python, see the fx-conversion-policy-v2 design
    report) and hard-coded here rather than derived from any code in this
    file. This is the strongest available proof that adding V2 support does
    not move any existing V1 conversion-policy identity."""
    content: dict[str, object] = {
        "schema_version": "fx-conversion-policy-v1",
        "policy_name": "INITIAL_CONVERSION_AND_REPORTING_MARK_V1",
        "model_version": "test-only-v1",
        "base_currency": "EUR",
        "trading_currency": "USD",
        "quote_convention": FxQuoteConvention.DECLARED_REFERENCE,
        "maximum_observation_staleness_seconds": 60,
        "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
    }
    expected_id = "sha256:ce35dd1944098cea11513d1c49c29acacbbdd3303e6f9785dd1ed2ea8ff9147c"
    assert str(calculate_fx_conversion_policy_id(content)) == expected_id
    policy = FxConversionPolicyConfiguration.model_validate(
        {"fx_conversion_policy_id": expected_id, **content}
    )
    assert str(policy.fx_conversion_policy_id) == expected_id


# --- fx-conversion-policy-v2: required transactional quote side ------------


def _conversion_policy_v2(**changes: object) -> FxConversionPolicyConfiguration:
    content: dict[str, object] = {
        "schema_version": "fx-conversion-policy-v2",
        "policy_name": "INITIAL_CONVERSION_AND_REPORTING_MARK_V1",
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


def test_v1_conversion_policy_forbids_conversion_direction() -> None:
    with pytest.raises(ValidationError, match="V1 conversion policy forbids it"):
        _policy(conversion_direction=FxConversionDirection.SELL_BASE_FOR_TRADING)


def test_v2_conversion_policy_requires_conversion_direction() -> None:
    with pytest.raises(ValidationError, match="requires conversion_direction"):
        _conversion_policy_v2(conversion_direction=None)


def test_v2_conversion_policy_accepts_bid_for_sell_base_for_trading() -> None:
    policy = _conversion_policy_v2(
        conversion_direction=FxConversionDirection.SELL_BASE_FOR_TRADING,
        quote_convention=FxQuoteConvention.BID,
    )
    assert policy.quote_convention is FxQuoteConvention.BID
    assert policy.conversion_direction is FxConversionDirection.SELL_BASE_FOR_TRADING


@pytest.mark.parametrize(
    "wrong_side",
    [FxQuoteConvention.MID, FxQuoteConvention.ASK, FxQuoteConvention.DECLARED_REFERENCE],
)
def test_v2_conversion_policy_rejects_non_bid_for_sell_base_for_trading(
    wrong_side: FxQuoteConvention,
) -> None:
    with pytest.raises(ValidationError, match="requires quote_convention"):
        _conversion_policy_v2(quote_convention=wrong_side)


def test_v2_conversion_policy_rejects_unsupported_direction() -> None:
    """Fail-closed by construction: no direction other than the one owner-approved
    enum member can even be parsed."""
    with pytest.raises(ValidationError):
        _conversion_policy_v2(conversion_direction="SELL_TRADING_FOR_BASE")


def test_v2_conversion_policy_identity_differs_from_equivalent_v1() -> None:
    v1_content: dict[str, object] = {
        "schema_version": "fx-conversion-policy-v1",
        "policy_name": "INITIAL_CONVERSION_AND_REPORTING_MARK_V1",
        "model_version": "test-only-v1",
        "base_currency": "EUR",
        "trading_currency": "USD",
        "quote_convention": FxQuoteConvention.BID,
        "maximum_observation_staleness_seconds": 60,
        "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
    }
    v1_id = calculate_fx_conversion_policy_id(v1_content)
    v2_policy = _conversion_policy_v2(quote_convention=FxQuoteConvention.BID)
    assert v1_id != v2_policy.fx_conversion_policy_id


def test_v2_conversion_policy_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _conversion_policy_v2(unexpected_field="not allowed")


def test_v2_conversion_policy_rejects_forged_identity() -> None:
    content: dict[str, object] = {
        "schema_version": "fx-conversion-policy-v2",
        "policy_name": "INITIAL_CONVERSION_AND_REPORTING_MARK_V1",
        "model_version": "test-only-v1",
        "base_currency": "EUR",
        "trading_currency": "USD",
        "quote_convention": FxQuoteConvention.BID,
        "maximum_observation_staleness_seconds": 60,
        "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
        "conversion_direction": FxConversionDirection.SELL_BASE_FOR_TRADING,
    }
    with pytest.raises(ValidationError, match="identity does not match content"):
        FxConversionPolicyConfiguration.model_validate(
            {"fx_conversion_policy_id": "sha256:" + "0" * 64, **content}
        )


def test_conversion_selection_unchanged_with_v2_policy_selects_bid() -> None:
    """A qualifying V2 policy's quote_convention (guaranteed BID by
    construction) still flows through to select a matching BID observation."""
    policy = _conversion_policy_v2(quote_convention=FxQuoteConvention.BID)
    bid_observation = _eligible_observation(quote_convention=FxQuoteConvention.BID)
    result = select_eligible_fx_observation_for_conversion([bid_observation], policy, _T)
    assert result == bid_observation


def test_conversion_selection_unchanged_with_v2_policy_fails_closed_on_other_side() -> None:
    """Same policy, failure path: only a non-BID observation is available, so
    the function must still fail closed rather than accepting it (this is a
    data-availability outcome, distinct from the policy itself being
    unsupported)."""
    policy = _conversion_policy_v2(quote_convention=FxQuoteConvention.BID)
    ask_only = _eligible_observation(quote_convention=FxQuoteConvention.ASK)
    result = select_eligible_fx_observation_for_conversion([ask_only], policy, _T)
    assert isinstance(result, FxConversionQuoteUnavailable)
    assert result.reason is FxQuoteUnavailableReason.REQUIRED_QUOTE_SIDE_UNAVAILABLE
    assert result.fx_conversion_policy_id == policy.fx_conversion_policy_id


def test_existing_fx_observation_unavailable_contract_is_unmodified() -> None:
    """This turn must not change FxObservationUnavailable's existing shape."""
    assert set(FxObservationUnavailable.model_fields) == {
        "reason",
        "evaluated_at",
        "fx_conversion_policy_id",
    }


def test_existing_causal_selection_function_is_behaviorally_unchanged() -> None:
    """select_eligible_fx_observation still ignores quote_convention entirely,
    exactly as before this turn's additions."""
    policy = _selection_policy(quote_convention=FxQuoteConvention.DECLARED_REFERENCE)
    observation = _eligible_observation(quote_convention=FxQuoteConvention.ASK)
    result = select_eligible_fx_observation([observation], policy, _T)
    assert result == observation
    assert isinstance(result, FxObservationReference)


# --- calculate_fx_conversion (pure SELL_BASE_FOR_TRADING calculation) -------


def test_calculate_fx_conversion_cannot_accept_a_caller_selected_observation() -> None:
    """Structural proof of the anti-bypass boundary: calculate_fx_conversion
    has no parameter through which a caller could hand it an
    already-selected, non-conforming FxObservationReference. It only accepts
    the raw released prefix, the policy, the amount, minor-unit digits and
    evaluated_at -- the observation is always selected internally through
    select_eligible_fx_observation_for_conversion."""
    parameters = set(inspect.signature(calculate_fx_conversion).parameters)
    assert parameters == {
        "released_prefix",
        "policy",
        "base_amount",
        "trading_currency_minor_unit_digits",
        "evaluated_at",
    }
    assert not any("observation" in name for name in parameters)


def test_calculate_fx_conversion_valid_v2_eur_usd_bid() -> None:
    """A qualifying V2 BID policy and one eligible BID observation produce a
    calculation referencing exactly that policy and that observation."""
    policy = _conversion_policy_v2()
    observation = _eligible_observation(quote_convention=FxQuoteConvention.BID, rate="1.08375")
    result = calculate_fx_conversion([observation], policy, Decimal("100"), 2, _T)
    assert isinstance(result, FxConversionCalculation)
    assert result.fx_conversion_policy_id == policy.fx_conversion_policy_id
    assert result.fx_observation_id == observation.fx_observation_id
    assert result.base_currency == "EUR"
    assert result.trading_currency == "USD"
    assert result.base_amount == Decimal("100")
    assert result.rate == Decimal("1.08375")
    assert result.evaluated_at == _T


def test_calculate_fx_conversion_exact_and_rounded_amounts_are_distinguished() -> None:
    """base_amount * rate = 100 * 1.08375 = 108.37500 exactly (no rounding
    needed for the exact multiplication at 34-digit precision). Quantizing
    to 2 minor-unit digits with ROUND_HALF_EVEN rounds the exact halfway
    value 108.375 up to the even digit, 108.38 -- distinct from the exact,
    unrounded 108.37500."""
    policy = _conversion_policy_v2()
    observation = _eligible_observation(quote_convention=FxQuoteConvention.BID, rate="1.08375")
    result = calculate_fx_conversion([observation], policy, Decimal("100"), 2, _T)
    assert isinstance(result, FxConversionCalculation)
    assert result.exact_trading_amount == Decimal("108.37500")
    assert result.rounded_trading_amount == Decimal("108.38")
    assert result.exact_trading_amount != result.rounded_trading_amount
    assert result.trading_currency_minor_unit_digits == 2
    assert result.rounding_policy is CostRoundingPolicy.ROUND_HALF_EVEN_V1


@pytest.mark.parametrize(
    ("minor_unit_digits", "rate", "base_amount", "expected_exact", "expected_rounded"),
    [
        (0, "163.5", "50", Decimal("8175.0"), Decimal("8175")),
        (3, "1.234565", "10", Decimal("12.345650"), Decimal("12.346")),
    ],
)
def test_calculate_fx_conversion_supports_non_two_decimal_minor_units(
    minor_unit_digits: int,
    rate: str,
    base_amount: str,
    expected_exact: Decimal,
    expected_rounded: Decimal,
) -> None:
    """No two-decimal-place assumption: a 0-minor-unit and a 3-minor-unit
    currency both quantize correctly at their own explicit, caller-supplied
    trading_currency_minor_unit_digits."""
    policy = _conversion_policy_v2()
    observation = _eligible_observation(quote_convention=FxQuoteConvention.BID, rate=rate)
    result = calculate_fx_conversion(
        [observation], policy, Decimal(base_amount), minor_unit_digits, _T
    )
    assert isinstance(result, FxConversionCalculation)
    assert result.exact_trading_amount == expected_exact
    assert result.rounded_trading_amount == expected_rounded


def test_calculate_fx_conversion_has_no_default_minor_unit_digits() -> None:
    """trading_currency_minor_unit_digits is a required positional/keyword
    argument with no default -- it must always be supplied explicitly."""
    parameter = inspect.signature(calculate_fx_conversion).parameters[
        "trading_currency_minor_unit_digits"
    ]
    assert parameter.default is inspect.Parameter.empty


def test_calculate_fx_conversion_rejects_v1_eur_usd_ask_bypass() -> None:
    """Reproduces Codex's exact confirmed V1 EUR/USD ASK bypass at the
    calculation boundary too: calculate_fx_conversion must reject a V1 policy
    exactly like select_eligible_fx_observation_for_conversion does, since it
    delegates directly to that same selector."""
    v1_ask_policy = _policy(
        base_currency="EUR", trading_currency="USD", quote_convention=FxQuoteConvention.ASK
    )
    assert v1_ask_policy.schema_version == "fx-conversion-policy-v1"
    ask_observation = _eligible_observation(quote_convention=FxQuoteConvention.ASK)
    with pytest.raises(FxConversionPolicyUnsupportedError, match="fx-conversion-policy-v2"):
        calculate_fx_conversion([ask_observation], v1_ask_policy, Decimal("100"), 2, _T)


def test_calculate_fx_conversion_rejects_v1_even_with_coincidentally_correct_bid() -> None:
    v1_bid_policy = _policy(
        base_currency="EUR", trading_currency="USD", quote_convention=FxQuoteConvention.BID
    )
    bid_observation = _eligible_observation(quote_convention=FxQuoteConvention.BID)
    with pytest.raises(FxConversionPolicyUnsupportedError):
        calculate_fx_conversion([bid_observation], v1_bid_policy, Decimal("100"), 2, _T)


@pytest.mark.parametrize(
    "available_convention",
    [FxQuoteConvention.ASK, FxQuoteConvention.MID, FxQuoteConvention.DECLARED_REFERENCE],
)
def test_calculate_fx_conversion_never_substitutes_a_different_side_for_bid(
    available_convention: FxQuoteConvention,
) -> None:
    """ASK, MID and DECLARED_REFERENCE observations must never be substituted
    for the required BID side; the calculation must fail closed with typed
    evidence rather than computing against the wrong quote."""
    policy = _conversion_policy_v2()
    wrong_side_observation = _eligible_observation(quote_convention=available_convention)
    result = calculate_fx_conversion([wrong_side_observation], policy, Decimal("100"), 2, _T)
    assert isinstance(result, FxConversionQuoteUnavailable)
    assert result.reason is FxQuoteUnavailableReason.REQUIRED_QUOTE_SIDE_UNAVAILABLE
    assert result.fx_conversion_policy_id == policy.fx_conversion_policy_id


def test_calculate_fx_conversion_fails_closed_when_no_observation_at_all() -> None:
    policy = _conversion_policy_v2()
    result = calculate_fx_conversion([], policy, Decimal("100"), 2, _T)
    assert isinstance(result, FxConversionQuoteUnavailable)
    assert result.reason is FxQuoteUnavailableReason.NO_ELIGIBLE_OBSERVATION


def test_calculate_fx_conversion_fails_closed_on_stale_observation() -> None:
    policy = _conversion_policy_v2(maximum_observation_staleness_seconds=60)
    stale_observation = _eligible_observation(
        quote_convention=FxQuoteConvention.BID,
        observed_at=_T - timedelta(seconds=1000),
        available_at=_T,
    )
    result = calculate_fx_conversion([stale_observation], policy, Decimal("100"), 2, _T)
    assert isinstance(result, FxConversionQuoteUnavailable)
    assert result.reason is FxQuoteUnavailableReason.NO_ELIGIBLE_OBSERVATION


def test_calculate_fx_conversion_fails_closed_on_unreleased_observation() -> None:
    policy = _conversion_policy_v2()
    unreleased_observation = _eligible_observation(
        quote_convention=FxQuoteConvention.BID, available_at=_T + timedelta(seconds=1)
    )
    result = calculate_fx_conversion([unreleased_observation], policy, Decimal("100"), 2, _T)
    assert isinstance(result, FxConversionQuoteUnavailable)
    assert result.reason is FxQuoteUnavailableReason.NO_ELIGIBLE_OBSERVATION


@pytest.mark.parametrize(
    "quality_status", [FxObservationQualityStatus.UNVALIDATED, FxObservationQualityStatus.SUSPECT]
)
def test_calculate_fx_conversion_fails_closed_on_non_validated_quality(
    quality_status: FxObservationQualityStatus,
) -> None:
    policy = _conversion_policy_v2()
    observation = _eligible_observation(
        quote_convention=FxQuoteConvention.BID, quality_status=quality_status
    )
    result = calculate_fx_conversion([observation], policy, Decimal("100"), 2, _T)
    assert isinstance(result, FxConversionQuoteUnavailable)
    assert result.reason is FxQuoteUnavailableReason.NO_ELIGIBLE_OBSERVATION


def test_calculate_fx_conversion_fails_closed_on_currency_mismatch() -> None:
    """An observation for a different currency pair is never eligible,
    regardless of quote side."""
    policy = _conversion_policy_v2(base_currency="EUR", trading_currency="USD")
    wrong_pair_observation = _eligible_observation(
        quote_convention=FxQuoteConvention.BID, base_currency="EUR", quote_currency="GBP"
    )
    result = calculate_fx_conversion([wrong_pair_observation], policy, Decimal("100"), 2, _T)
    assert isinstance(result, FxConversionQuoteUnavailable)
    assert result.reason is FxQuoteUnavailableReason.NO_ELIGIBLE_OBSERVATION


@pytest.mark.parametrize("invalid_amount", ["0", "-1", "-100.50"])
def test_calculate_fx_conversion_rejects_zero_and_negative_amounts(invalid_amount: str) -> None:
    policy = _conversion_policy_v2()
    observation = _eligible_observation(quote_convention=FxQuoteConvention.BID)
    with pytest.raises(FxConversionInputError, match="positive"):
        calculate_fx_conversion([observation], policy, Decimal(invalid_amount), 2, _T)


def test_calculate_fx_conversion_rejects_float_amount() -> None:
    policy = _conversion_policy_v2()
    observation = _eligible_observation(quote_convention=FxQuoteConvention.BID)
    with pytest.raises(FxConversionInputError, match="float"):
        calculate_fx_conversion([observation], policy, 100.0, 2, _T)  # type: ignore[arg-type]


@pytest.mark.parametrize("non_finite", ["NaN", "Infinity", "-Infinity"])
def test_calculate_fx_conversion_rejects_non_finite_amount(non_finite: str) -> None:
    policy = _conversion_policy_v2()
    observation = _eligible_observation(quote_convention=FxQuoteConvention.BID)
    with pytest.raises(FxConversionInputError, match="finite"):
        calculate_fx_conversion([observation], policy, Decimal(non_finite), 2, _T)


def test_calculate_fx_conversion_rejects_negative_minor_unit_digits() -> None:
    policy = _conversion_policy_v2()
    observation = _eligible_observation(quote_convention=FxQuoteConvention.BID)
    with pytest.raises(FxConversionInputError, match="minor_unit_digits"):
        calculate_fx_conversion([observation], policy, Decimal("100"), -1, _T)


@pytest.mark.parametrize(
    ("label", "invalid_minor_unit_digits"),
    [
        ("bool True", True),
        ("bool False", False),
        ("float", 2.5),
        ("string", "2"),
        ("None", None),
    ],
)
def test_calculate_fx_conversion_rejects_non_genuine_int_minor_unit_digits(
    label: str, invalid_minor_unit_digits: object
) -> None:
    """bool is a Python int subclass (and Pydantic's default lax int
    validation accepts it too) but must never be silently treated as a
    precision of 0 or 1; no other non-int type is accepted either."""
    policy = _conversion_policy_v2()
    observation = _eligible_observation(quote_convention=FxQuoteConvention.BID)
    with pytest.raises(FxConversionInputError, match="genuine int"):
        calculate_fx_conversion(
            [observation],
            policy,
            Decimal("100"),
            invalid_minor_unit_digits,  # type: ignore[arg-type]
            _T,
        )


def test_calculate_fx_conversion_rejects_excessively_large_minor_unit_digits() -> None:
    """A very large minor-unit-digit count fails closed with a typed,
    documented FxConversionInputError rather than an unexpected raw Decimal
    exception, and is never silently clamped to a smaller value."""
    policy = _conversion_policy_v2()
    observation = _eligible_observation(quote_convention=FxQuoteConvention.BID)
    with pytest.raises(FxConversionInputError, match="cannot be quantized"):
        calculate_fx_conversion([observation], policy, Decimal("100"), 10**6, _T)


def test_calculate_fx_conversion_fails_closed_when_multiplication_needs_more_than_34_digits() -> (
    None
):
    """base_amount and rate each carry 18 significant digits; their true
    product needs 36 significant digits and cannot be represented exactly at
    this project's approved 34-digit precision. calculate_fx_conversion must
    fail closed with FxConversionInputError rather than silently returning a
    rounded value labeled exact_trading_amount."""
    policy = _conversion_policy_v2()
    observation = _eligible_observation(
        quote_convention=FxQuoteConvention.BID, rate="987654321.123456789"
    )
    with pytest.raises(FxConversionInputError, match="cannot be represented exactly"):
        calculate_fx_conversion([observation], policy, Decimal("123456789012345678"), 2, _T)


def test_calculate_fx_conversion_succeeds_when_multiplication_fits_within_34_digits() -> None:
    """The same shape of calculation succeeds, with a genuinely exact
    exact_trading_amount, whenever the true product needs no more than 34
    significant digits."""
    policy = _conversion_policy_v2()
    observation = _eligible_observation(quote_convention=FxQuoteConvention.BID, rate="1.08375")
    result = calculate_fx_conversion([observation], policy, Decimal("100"), 2, _T)
    assert isinstance(result, FxConversionCalculation)
    assert result.exact_trading_amount == Decimal("108.37500")


def test_calculate_fx_conversion_result_validator_rejects_a_precision_losing_exact_amount() -> None:
    """Direct-construction proof that FxConversionCalculation's own validator
    cannot be tricked into accepting a silently-rounded product as exact: it
    recomputes exact_trading_amount through the same Inexact-trapping
    _exact_multiply helper calculate_fx_conversion uses, not through a
    separate context that could reproduce the same precision loss."""
    base_amount = Decimal("123456789012345678")
    rate = Decimal("987654321.123456789")
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        silently_rounded_product = base_amount * rate
    with pytest.raises(ValidationError, match="cannot be represented exactly"):
        FxConversionCalculation(
            fx_conversion_policy_id=FxConversionPolicyId.parse("sha256:" + "0" * 64),
            fx_observation_id=FxObservationId.parse("sha256:" + "1" * 64),
            base_currency="EUR",
            trading_currency="USD",
            base_amount=base_amount,
            rate=rate,
            evaluated_at=_T,
            exact_trading_amount=silently_rounded_product,
            trading_currency_minor_unit_digits=2,
            rounding_policy=CostRoundingPolicy.ROUND_HALF_EVEN_V1,
            rounded_trading_amount=Decimal("121932631140070109974089316.76"),
        )


def test_calculate_fx_conversion_still_enforces_v2_bid_causal_selection_after_the_fix() -> None:
    """Re-confirms, after the numerical-safety fix, that the V1-bypass
    rejection, the required-BID-side enforcement and the causal-eligibility
    rules are all still exercised through the same, unmodified
    select_eligible_fx_observation_for_conversion delegation."""
    v1_ask_policy = _policy(
        base_currency="EUR", trading_currency="USD", quote_convention=FxQuoteConvention.ASK
    )
    ask_observation = _eligible_observation(quote_convention=FxQuoteConvention.ASK)
    with pytest.raises(FxConversionPolicyUnsupportedError):
        calculate_fx_conversion([ask_observation], v1_ask_policy, Decimal("100"), 2, _T)

    v2_policy = _conversion_policy_v2()
    result = calculate_fx_conversion([ask_observation], v2_policy, Decimal("100"), 2, _T)
    assert isinstance(result, FxConversionQuoteUnavailable)
    assert result.reason is FxQuoteUnavailableReason.REQUIRED_QUOTE_SIDE_UNAVAILABLE

    bid_observation = _eligible_observation(quote_convention=FxQuoteConvention.BID, rate="1.08375")
    ok_result = calculate_fx_conversion([bid_observation], v2_policy, Decimal("100"), 2, _T)
    assert isinstance(ok_result, FxConversionCalculation)
    assert ok_result.fx_observation_id == bid_observation.fx_observation_id


def test_calculate_fx_conversion_is_deterministic() -> None:
    """Calculating twice from identical inputs produces an identical result."""
    policy = _conversion_policy_v2()
    observation = _eligible_observation(quote_convention=FxQuoteConvention.BID, rate="1.08375")
    first = calculate_fx_conversion([observation], policy, Decimal("100"), 2, _T)
    second = calculate_fx_conversion([observation], policy, Decimal("100"), 2, _T)
    assert first == second


def test_calculate_fx_conversion_does_not_mint_a_new_identity_domain() -> None:
    """FxConversionCalculation is a plain evidence-shaped result, referencing
    existing policy/observation identities rather than carrying its own new
    content-identified primary key -- mirroring FxConversionQuoteUnavailable
    and FxObservationUnavailable."""
    assert "schema_version" in FxConversionCalculation.model_fields
    identity_like_fields = {
        name
        for name in FxConversionCalculation.model_fields
        if name.endswith("_id") and name not in {"fx_conversion_policy_id", "fx_observation_id"}
    }
    assert identity_like_fields == set()


def test_calculate_fx_conversion_does_not_change_existing_v1_or_v2_identity_fixtures() -> None:
    """Building on calculate_fx_conversion must not touch the pinned V1
    identity or the already-accepted V2 conversion-policy identity
    algorithm: both still round-trip through calculate_fx_conversion_policy_id
    exactly as constructed."""
    v1_policy = _policy(base_currency="EUR", trading_currency="USD")
    assert calculate_fx_conversion_policy_id(v1_policy) == v1_policy.fx_conversion_policy_id
    v2_policy = _conversion_policy_v2()
    assert calculate_fx_conversion_policy_id(v2_policy) == v2_policy.fx_conversion_policy_id


def test_calculate_fx_conversion_result_is_not_a_posted_or_executed_conversion() -> None:
    """Structural proof of the calculated-vs-executed boundary: the result
    type carries no capital-movement, balance, fill, order or posting
    field."""
    forbidden_substrings = ("balance", "capital", "fill", "order", "posted", "executed", "ledger")
    for field_name in FxConversionCalculation.model_fields:
        lowered = field_name.lower()
        assert not any(substring in lowered for substring in forbidden_substrings), field_name
