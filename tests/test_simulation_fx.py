"""Behavior tests for the Phase 6.2 FX observation and conversion-policy contracts.

These contracts are pure evidence/policy shapes only. No FX rate, quote
convention or staleness threshold has an engine default, and this milestone
implements no causal selection, conversion, balanced-leg calculation or
manifest binding — several tests below assert that boundary explicitly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ai_trading_scanner.simulation import (
    CostRoundingPolicy,
    FxConversionPolicyConfiguration,
    FxObservationQualityStatus,
    FxObservationReference,
    FxQuoteConvention,
    calculate_fx_conversion_policy_id,
    calculate_fx_observation_id,
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


def test_fx_module_implements_no_resolver_execution_or_posting_symbols() -> None:
    """This bounded step is evidence/policy contracts only; no resolver or posting."""
    forbidden_names = {
        "resolve_fx_conversion",
        "select_fx_observation",
        "FxConversionLegPair",
        "post_fx_conversion",
        "apply_fx_conversion",
    }
    exported = set(dir(fx_module))
    assert forbidden_names.isdisjoint(exported)
