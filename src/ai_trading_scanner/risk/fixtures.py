"""Tiny credential-free Phase 5 contract health fixture."""

from decimal import Decimal

from ai_trading_scanner.domain import (
    AccountId,
    AgentId,
    AllocationId,
    ConfigurationVersionId,
)
from ai_trading_scanner.risk.models import (
    AllocationSnapshot,
    ParentCapitalSnapshot,
    baseline_risk_configuration,
)


def validate_offline_risk_fixture() -> bool:
    """Validate identities, policy registration, and conservation without a trade."""
    authority_id = ConfigurationVersionId.parse("phase5-health-v1")
    policy = baseline_risk_configuration(authority_id)
    parent = ParentCapitalSnapshot(
        account_id=AccountId.parse("health:account"),
        currency="EUR",
        total_capital=Decimal("50"),
        available_capital=Decimal("50"),
    )
    allocation = AllocationSnapshot(
        allocation_id=AllocationId.parse("health:allocation"),
        account_id=parent.account_id,
        agent_id=AgentId.parse("health:agent"),
        configuration_version_id=authority_id,
        currency="EUR",
        allocated_capital=Decimal("50"),
        available_capital=Decimal("50"),
    )
    return (
        policy.profile_name == "BASELINE_RESEARCH_V1"
        and parent.total_capital == parent.available_capital
        and allocation.allocated_capital == allocation.available_capital
    )
