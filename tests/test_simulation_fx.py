"""Behavior tests for the Phase 6.2 FX observation and conversion-policy contracts.

These contracts are pure evidence/policy shapes only. No FX rate, quote
convention or staleness threshold has an engine default, and this milestone
implements no causal selection, conversion, balanced-leg calculation or
manifest binding — several tests below assert that boundary explicitly.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ai_trading_scanner.simulation import (
    CostRoundingPolicy,
    FxConversionPolicyConfiguration,
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
        "source_record_id": "fx:test-only:1",
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
    with pytest.raises(ValidationError, match="Decimal"):
        _observation(rate=1.08)


def test_observation_rejects_non_positive_rate() -> None:
    with pytest.raises(ValidationError):
        _observation(rate="0")
    with pytest.raises(ValidationError):
        _observation(rate="-1.08")


def test_observation_has_no_default_rate() -> None:
    content: dict[str, object] = {
        "schema_version": "fx-observation-reference-v1",
        "base_currency": "EUR",
        "quote_currency": "USD",
        "provider": "TEST_ONLY_SYNTHETIC_PROVIDER",
        "methodology_version": "test-only-v1",
        "quote_convention": FxQuoteConvention.DECLARED_REFERENCE,
        "observed_at": _OBSERVED_AT,
        "available_at": _AVAILABLE_AT,
    }
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
            {
                "fx_observation_id": "sha256:" + "0" * 64,
                "schema_version": "fx-observation-reference-v1",
                "base_currency": "EUR",
                "quote_currency": "USD",
                "provider": "TEST_ONLY_SYNTHETIC_PROVIDER",
                "methodology_version": "test-only-v1",
                "quote_convention": FxQuoteConvention.DECLARED_REFERENCE,
                "rate": "1.08",
                "observed_at": _OBSERVED_AT,
                "available_at": _AVAILABLE_AT,
            }
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
