"""Immutable, evidence-based cost sourcing and rounding-policy contracts for Phase 6.2.

Pure and evidence-only: this module registers and validates whether a
`TransactionCostConfiguration` is sourced and versioned. It never invents fee
values, never posts any economic effect, and never changes the identity or
behavior of the existing Phase 6 `TransactionCostConfiguration` contract.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_trading_scanner.domain import CostProfileRegistrationId, TransactionCostModelId
from ai_trading_scanner.domain.content_identity import sha256_content_id_v2
from ai_trading_scanner.simulation.models import TransactionCostConfiguration


def _identity_content(
    value: BaseModel | dict[str, object], identity_field: str
) -> dict[str, object]:
    if isinstance(value, BaseModel):
        content = value.model_dump(mode="python", exclude={identity_field})
    else:
        content = {key: item for key, item in value.items() if key != identity_field}
    for key, item in content.items():
        # The shared V2 canonicalizer handles datetime but not a bare calendar
        # date; normalize it to a stable ISO string here rather than widening
        # shared content-identity behavior for one field on one new contract.
        if isinstance(item, date) and not isinstance(item, datetime):
            content[key] = item.isoformat()
    return content


def _is_meaningful_text(value: str | None) -> bool:
    """True only for a non-`None` string with at least one non-whitespace character."""
    return value is not None and value.strip() != ""


class CostRoundingPolicy(StrEnum):
    """Versioned Decimal rounding rule for cost and FX monetary calculations.

    Formalizes the rounding behavior already used by the accepted Phase 6 V1/V2
    `calculate_fill_costs` (banker's rounding, `ROUND_HALF_EVEN`, at 34-digit
    precision) as an explicit, referenceable policy identity. Adopting this
    enum does not change `calculate_fill_costs`, `TransactionCostConfiguration`,
    or any existing V1/V2 content identity; it is additive, forward-looking
    configuration for the new cost/FX contracts introduced in Phase 6.2.
    """

    ROUND_HALF_EVEN_V1 = "ROUND_HALF_EVEN_V1"


class CostProfileStatus(StrEnum):
    """Sourcing state of one transaction-cost profile."""

    REQUIRES_SOURCING = "REQUIRES_SOURCING"
    SOURCED_AND_VALIDATED = "SOURCED_AND_VALIDATED"


class CostProfileRegistration(BaseModel):
    """Sourcing/audit envelope over one `TransactionCostConfiguration`.

    This never carries or duplicates the numeric fee schedule itself; it only
    references the configuration's own `cost_model_id` and records whether
    that exact configuration has been sourced from real evidence (e.g. a
    broker's published fee schedule) and by whom. It never modifies
    `TransactionCostConfiguration`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    registration_id: CostProfileRegistrationId
    schema_version: Literal["cost-profile-registration-v1"] = "cost-profile-registration-v1"
    cost_model_id: TransactionCostModelId
    profile_name: str = Field(min_length=1)
    status: CostProfileStatus
    rounding_policy: CostRoundingPolicy
    source: str | None = None
    source_reference: str | None = None
    effective_date: date | None = None
    validated_by: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_registration(self) -> Self:
        sourced = self.status is CostProfileStatus.SOURCED_AND_VALIDATED
        has_sourcing_evidence = (
            _is_meaningful_text(self.source)
            and _is_meaningful_text(self.source_reference)
            and self.effective_date is not None
            and _is_meaningful_text(self.validated_by)
        )
        if sourced != has_sourcing_evidence:
            raise ValueError(
                "a sourced-and-validated cost profile requires nonblank source, source "
                "reference, effective date and validator attribution; an unsourced profile "
                "must omit them or leave them blank"
            )
        if self.registration_id != calculate_cost_profile_registration_id(self):
            raise ValueError("cost profile registration identity does not match content")
        return self


def calculate_cost_profile_registration_id(
    registration: CostProfileRegistration | dict[str, object],
) -> CostProfileRegistrationId:
    return CostProfileRegistrationId.parse(
        sha256_content_id_v2(_identity_content(registration, "registration_id"))
    )


class CostProfileNotSourcedError(ValueError):
    """Raised when a run attempts to use an unsourced or mismatched cost profile."""


def require_sourced_cost_profile(
    registration: CostProfileRegistration,
    configuration: TransactionCostConfiguration,
) -> TransactionCostConfiguration:
    """Fail closed unless the exact configuration is registered as sourced and validated.

    `CostProfileRegistration.validate_registration` already makes a
    `SOURCED_AND_VALIDATED` instance impossible to construct with missing or
    blank evidence, so this re-checks that invariant defensively rather than
    trusting the status flag alone. Returns the configuration unchanged so
    callers can chain this as a gate; it never fabricates, adjusts or
    defaults any cost value.
    """
    if registration.cost_model_id != configuration.cost_model_id:
        raise CostProfileNotSourcedError(
            "cost profile registration does not reference the supplied configuration"
        )
    if registration.status is not CostProfileStatus.SOURCED_AND_VALIDATED or not (
        _is_meaningful_text(registration.source)
        and _is_meaningful_text(registration.source_reference)
        and registration.effective_date is not None
        and _is_meaningful_text(registration.validated_by)
    ):
        raise CostProfileNotSourcedError(
            f"cost profile {registration.profile_name!r} is not sourced and validated with "
            "complete, nonblank evidence; no run may use it"
        )
    return configuration
