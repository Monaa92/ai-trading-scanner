"""Behavior tests for the Phase 6.2 cost-profile sourcing/registration contracts."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError
from simulation_helpers import cost_configuration

from ai_trading_scanner.simulation import (
    CostProfileNotSourcedError,
    CostProfileRegistration,
    CostProfileStatus,
    CostRoundingPolicy,
    TransactionCostConfiguration,
    calculate_cost_model_id,
    calculate_cost_profile_registration_id,
    require_sourced_cost_profile,
)


def _registration(**changes: object) -> CostProfileRegistration:
    configuration = cost_configuration()
    content: dict[str, object] = {
        "schema_version": "cost-profile-registration-v1",
        "cost_model_id": configuration.cost_model_id,
        "profile_name": "TEST_ONLY_SYNTHETIC_PROFILE",
        "status": CostProfileStatus.REQUIRES_SOURCING,
        "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
        "source": None,
        "source_reference": None,
        "effective_date": None,
        "validated_by": None,
        "notes": None,
    }
    content.update(changes)
    return CostProfileRegistration.model_validate(
        {"registration_id": calculate_cost_profile_registration_id(content), **content}
    )


def test_unsourced_registration_forbids_sourcing_evidence() -> None:
    registered = _registration()
    assert registered.status is CostProfileStatus.REQUIRES_SOURCING
    with pytest.raises(ValidationError, match="unsourced profile must omit"):
        _registration(
            source="TEST_ONLY: not a real broker",
            source_reference="TEST_ONLY: fixture-ref-1",
            effective_date=date(2026, 1, 1),
            validated_by="test-fixture",
        )


def test_sourced_registration_requires_complete_sourcing_evidence() -> None:
    with pytest.raises(ValidationError, match="requires source"):
        _registration(status=CostProfileStatus.SOURCED_AND_VALIDATED)


def test_sourced_registration_accepts_complete_sourcing_evidence() -> None:
    registered = _registration(
        status=CostProfileStatus.SOURCED_AND_VALIDATED,
        source="TEST_ONLY: synthetic fixture, not a real broker fee schedule",
        source_reference="TEST_ONLY: fixture-ref-1",
        effective_date=date(2026, 1, 1),
        validated_by="test-fixture",
    )
    assert registered.status is CostProfileStatus.SOURCED_AND_VALIDATED


def test_registration_identity_is_stable_for_identical_content() -> None:
    first = _registration()
    second = _registration()
    assert first.registration_id == second.registration_id
    assert first == second


def test_registration_identity_changes_with_profile_name() -> None:
    first = _registration()
    second = _registration(profile_name="TEST_ONLY_OTHER_PROFILE")
    assert first.registration_id != second.registration_id


def test_registration_identity_changes_with_status_and_evidence() -> None:
    unsourced = _registration()
    sourced = _registration(
        status=CostProfileStatus.SOURCED_AND_VALIDATED,
        source="TEST_ONLY: synthetic fixture, not a real broker fee schedule",
        source_reference="TEST_ONLY: fixture-ref-1",
        effective_date=date(2026, 1, 1),
        validated_by="test-fixture",
    )
    assert unsourced.registration_id != sourced.registration_id


def test_registration_rejects_forged_identity() -> None:
    configuration = cost_configuration()
    content: dict[str, object] = {
        "schema_version": "cost-profile-registration-v1",
        "cost_model_id": configuration.cost_model_id,
        "profile_name": "TEST_ONLY_SYNTHETIC_PROFILE",
        "status": CostProfileStatus.REQUIRES_SOURCING,
        "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
    }
    with pytest.raises(ValidationError, match="identity does not match content"):
        CostProfileRegistration.model_validate(
            {"registration_id": "sha256:" + "0" * 64, **content}
        )


def test_registration_rejects_unknown_fields() -> None:
    configuration = cost_configuration()
    content: dict[str, object] = {
        "schema_version": "cost-profile-registration-v1",
        "cost_model_id": configuration.cost_model_id,
        "profile_name": "TEST_ONLY_SYNTHETIC_PROFILE",
        "status": CostProfileStatus.REQUIRES_SOURCING,
        "rounding_policy": CostRoundingPolicy.ROUND_HALF_EVEN_V1,
        "unexpected_field": "not allowed",
    }
    with pytest.raises(ValidationError):
        CostProfileRegistration.model_validate(
            {"registration_id": calculate_cost_profile_registration_id(content), **content}
        )


def test_require_sourced_cost_profile_blocks_unsourced_profile() -> None:
    configuration = cost_configuration()
    registration = _registration(cost_model_id=configuration.cost_model_id)
    with pytest.raises(CostProfileNotSourcedError, match="not sourced and validated"):
        require_sourced_cost_profile(registration, configuration)


def test_require_sourced_cost_profile_blocks_mismatched_configuration() -> None:
    configuration = cost_configuration()
    other_configuration = cost_configuration(profile_name="TEST_ONLY_OTHER")
    registration = _registration(
        cost_model_id=configuration.cost_model_id,
        status=CostProfileStatus.SOURCED_AND_VALIDATED,
        source="TEST_ONLY: synthetic fixture, not a real broker fee schedule",
        source_reference="TEST_ONLY: fixture-ref-1",
        effective_date=date(2026, 1, 1),
        validated_by="test-fixture",
    )
    with pytest.raises(CostProfileNotSourcedError, match="does not reference"):
        require_sourced_cost_profile(registration, other_configuration)


def test_require_sourced_cost_profile_returns_configuration_when_sourced() -> None:
    configuration = cost_configuration()
    registration = _registration(
        cost_model_id=configuration.cost_model_id,
        status=CostProfileStatus.SOURCED_AND_VALIDATED,
        source="TEST_ONLY: synthetic fixture, not a real broker fee schedule",
        source_reference="TEST_ONLY: fixture-ref-1",
        effective_date=date(2026, 1, 1),
        validated_by="test-fixture",
    )
    assert require_sourced_cost_profile(registration, configuration) is configuration


def test_existing_transaction_cost_configuration_is_unmodified_by_registration_module() -> None:
    """Phase 6.2 must not silently change the accepted TransactionCostConfiguration."""
    assert set(TransactionCostConfiguration.model_fields) == {
        "cost_model_id",
        "schema_version",
        "profile_name",
        "profile_version",
        "currency",
        "minimum_commission_per_order",
        "commission_per_share",
        "spread_bps",
        "slippage_bps",
        "other_fee_bps",
    }
    configuration = cost_configuration()
    assert configuration.cost_model_id == calculate_cost_model_id(configuration)
