from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from risk_helpers import AUTHORITY_ID, risk_policy

from ai_trading_scanner.domain import AccountId, RiskConfigurationId
from ai_trading_scanner.domain.execution import ApprovalPolicy, ExecutionEnvironment
from ai_trading_scanner.risk import (
    AllocationSnapshot,
    ParentCapitalSnapshot,
    RiskConfiguration,
    RiskPolicyStatus,
    SafetyLockReason,
    SafetyLockScope,
    baseline_risk_configuration,
    calculate_risk_configuration_id,
    create_safety_lock,
)


def test_baseline_is_versioned_unvalidated_research_policy() -> None:
    configured = baseline_risk_configuration(AUTHORITY_ID)

    assert configured.profile_name == "BASELINE_RESEARCH_V1"
    assert configured.status is RiskPolicyStatus.RESEARCH_ONLY
    assert configured.max_risk_fraction == Decimal("0.01")
    assert configured.max_agent_drawdown_fraction == Decimal("0.03")
    assert configured.risk_configuration_id == calculate_risk_configuration_id(configured)


@pytest.mark.parametrize(
    "field",
    [
        "max_risk_fraction",
        "max_monetary_risk",
        "max_position_fraction",
        "max_agent_exposure_fraction",
        "max_parent_exposure_fraction",
        "max_instrument_exposure_fraction",
        "max_agent_drawdown_fraction",
        "max_parent_drawdown_fraction",
        "quantity_increment",
    ],
)
def test_risk_configuration_rejects_binary_float(field: str) -> None:
    with pytest.raises(ValidationError, match="must not use float"):
        risk_policy(**{field: 0.5})


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-0.1")])
def test_risk_configuration_rejects_invalid_decimal(value: Decimal) -> None:
    with pytest.raises(ValidationError):
        risk_policy(max_risk_fraction=value)


def test_risk_fraction_cannot_exceed_one() -> None:
    with pytest.raises(ValidationError):
        risk_policy(max_risk_fraction=Decimal("1.0001"))


def test_phase5_configuration_cannot_enable_live() -> None:
    with pytest.raises(ValidationError, match="cannot enable LIVE"):
        risk_policy(
            allowed_execution_environments=(
                ExecutionEnvironment.LIVE,
                ExecutionEnvironment.SIMULATION,
            )
        )


def test_paper_and_full_auto_remain_independent_representable_dimensions() -> None:
    configured = risk_policy(
        allowed_execution_environments=(
            ExecutionEnvironment.PAPER,
            ExecutionEnvironment.SIMULATION,
        ),
        allowed_approval_policies=(
            ApprovalPolicy.FULL_AUTO,
            ApprovalPolicy.MANUAL_APPROVAL,
        ),
    )

    assert ExecutionEnvironment.PAPER in configured.allowed_execution_environments
    assert ApprovalPolicy.FULL_AUTO in configured.allowed_approval_policies
    assert ExecutionEnvironment.LIVE not in configured.allowed_execution_environments


def test_risk_configuration_identity_rejects_content_mutation() -> None:
    configured = risk_policy()
    content = configured.model_dump(mode="python")
    content["max_risk_fraction"] = Decimal("0.5")

    with pytest.raises(ValidationError, match="identity"):
        RiskConfiguration.model_validate(content)


def test_capital_snapshots_reject_float_and_broken_conservation() -> None:
    with pytest.raises(ValidationError, match="must not use float"):
        ParentCapitalSnapshot.model_validate(
            {
                "account_id": "account:test",
                "currency": "USD",
                "total_capital": 100.0,
                "available_capital": 100.0,
            }
        )
    with pytest.raises(ValidationError, match="conservation"):
        AllocationSnapshot.model_validate(
            {
                "allocation_id": "allocation:A",
                "account_id": "account:test",
                "agent_id": "agent:A",
                "configuration_version_id": AUTHORITY_ID,
                "currency": "USD",
                "allocated_capital": Decimal("100"),
                "available_capital": Decimal("99"),
            }
        )


def test_identifier_types_remain_distinct() -> None:
    configured = risk_policy()

    assert isinstance(configured.risk_configuration_id, RiskConfigurationId)


def test_risk_configuration_rejects_noncanonical_environment_and_policy_lists() -> None:
    with pytest.raises(ValidationError, match="environments must be unique and canonical"):
        risk_policy(
            allowed_execution_environments=(
                ExecutionEnvironment.SIMULATION,
                ExecutionEnvironment.PAPER,
            )
        )
    with pytest.raises(ValidationError, match="policies must be unique and canonical"):
        risk_policy(
            allowed_approval_policies=(
                ApprovalPolicy.MANUAL_APPROVAL,
                ApprovalPolicy.FULL_AUTO,
            )
        )


def test_safety_lock_scope_requires_typed_owner_context() -> None:
    with pytest.raises(ValidationError, match="agent lock requires"):
        create_safety_lock(
            scope=SafetyLockScope.AGENT,
            reason=SafetyLockReason.TRADING_LOCK,
            account_id=AccountId.parse("account:test"),
            activated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
