from datetime import timedelta
from decimal import Decimal

import pytest
from risk_helpers import (
    allocation_snapshot,
    parent_snapshot,
    risk_policy,
    safety_state,
    state,
    trade_proposal,
)

from ai_trading_scanner.domain.execution import (
    ApprovalPolicy,
    ExecutionEnvironment,
    SubmissionMode,
)
from ai_trading_scanner.risk import (
    RiskDecisionStatus,
    RiskEngine,
    RiskRejectionCode,
)
from ai_trading_scanner.strategies import TradeProposal, calculate_trade_proposal_id


def test_decimal_sizing_is_deterministic_and_risk_bounded() -> None:
    proposal = trade_proposal()
    configured = risk_policy(
        max_risk_fraction=Decimal("0.01"), quantity_increment=Decimal("0.0001")
    )
    snapshot = state()

    first = RiskEngine().evaluate(proposal, configured, snapshot, evaluated_at=proposal.as_of)
    second = RiskEngine().evaluate(proposal, configured, snapshot, evaluated_at=proposal.as_of)

    assert first == second
    assert first.status is RiskDecisionStatus.APPROVED_FOR_RESERVATION
    assert first.sizing_decision is not None
    assert first.sizing_decision.modeled_risk_amount <= Decimal("1")
    assert first.sizing_decision.quantity % Decimal("0.0001") == 0


def test_rounding_is_downward_and_never_increases_risk() -> None:
    proposal = trade_proposal()
    configured = risk_policy(max_risk_fraction=Decimal("0.01"), quantity_increment=Decimal("0.1"))
    decision = RiskEngine().evaluate(proposal, configured, state(), evaluated_at=proposal.as_of)

    sizing = decision.sizing_decision
    assert sizing is not None
    raw_quantity = sizing.allowed_risk_amount / sizing.unit_modeled_loss
    assert sizing.quantity <= raw_quantity
    assert sizing.modeled_risk_amount <= sizing.allowed_risk_amount


def test_exact_final_quantity_is_never_silently_reduced() -> None:
    proposal = trade_proposal(final_quantity=Decimal("1"))
    configured = risk_policy(max_risk_fraction=Decimal("0.01"), quantity_increment=Decimal("0.1"))
    decision = RiskEngine().evaluate(proposal, configured, state(), evaluated_at=proposal.as_of)

    assert decision.status is RiskDecisionStatus.REJECTED
    assert RiskRejectionCode.RISK_PER_TRADE_EXCEEDED in decision.reason_codes


def test_final_quantity_must_match_generic_increment() -> None:
    proposal = trade_proposal(final_quantity=Decimal("0.75"))
    decision = RiskEngine().evaluate(
        proposal,
        risk_policy(quantity_increment=Decimal("0.1")),
        state(),
        evaluated_at=proposal.as_of,
    )

    assert decision.reason_codes == (RiskRejectionCode.INVALID_PROPOSAL,)


def test_available_capital_position_agent_parent_and_concentration_caps_fail_closed() -> None:
    proposal = trade_proposal(final_quantity=Decimal("0.7"))
    cases = (
        (
            risk_policy(),
            state(parent=parent_snapshot("50"), allocation=allocation_snapshot(capital="100")),
            RiskRejectionCode.INSUFFICIENT_AVAILABLE_CAPITAL,
        ),
        (
            risk_policy(max_position_fraction=Decimal("0.5")),
            state(),
            RiskRejectionCode.POSITION_SIZE_EXCEEDED,
        ),
        (
            risk_policy(max_agent_exposure_fraction=Decimal("0.5")),
            state(),
            RiskRejectionCode.AGENT_EXPOSURE_EXCEEDED,
        ),
        (
            risk_policy(max_parent_exposure_fraction=Decimal("0.5")),
            state(),
            RiskRejectionCode.PARENT_EXPOSURE_EXCEEDED,
        ),
        (
            risk_policy(max_instrument_exposure_fraction=Decimal("0.5")),
            state(),
            RiskRejectionCode.INSTRUMENT_CONCENTRATION_EXCEEDED,
        ),
    )
    for configured, snapshot, expected in cases:
        decision = RiskEngine().evaluate(
            proposal,
            configured,
            snapshot,
            evaluated_at=proposal.as_of,
        )
        assert decision.status is RiskDecisionStatus.REJECTED
        assert expected in decision.reason_codes


def test_ownership_configuration_and_currency_mismatches_are_structured() -> None:
    proposal = trade_proposal(agent="agent:A")
    wrong_owner = allocation_snapshot(agent="agent:B")
    wrong_config = wrong_owner.model_copy(
        update={"configuration_version_id": "different-config-v1"}
    )
    wrong_currency = wrong_owner.model_copy(update={"currency": "EUR"})

    owner_decision = RiskEngine().evaluate(
        proposal, risk_policy(), state(allocation=wrong_owner), evaluated_at=proposal.as_of
    )
    config_decision = RiskEngine().evaluate(
        proposal, risk_policy(), state(allocation=wrong_config), evaluated_at=proposal.as_of
    )
    currency_decision = RiskEngine().evaluate(
        proposal, risk_policy(), state(allocation=wrong_currency), evaluated_at=proposal.as_of
    )

    assert RiskRejectionCode.OWNERSHIP_MISMATCH in owner_decision.reason_codes
    assert RiskRejectionCode.CONFIGURATION_MISMATCH in config_decision.reason_codes
    assert RiskRejectionCode.CURRENCY_MISMATCH in currency_decision.reason_codes


def test_expired_stale_and_future_proposals_fail_with_distinct_codes() -> None:
    proposal = trade_proposal(validity_extension_minutes=30)
    engine = RiskEngine()
    expired = engine.evaluate(
        proposal,
        risk_policy(),
        state(),
        evaluated_at=proposal.valid_until,
    )
    stale = engine.evaluate(
        proposal,
        risk_policy(max_proposal_age_seconds=1),
        state(),
        evaluated_at=proposal.as_of + timedelta(seconds=2),
    )
    future = engine.evaluate(
        proposal,
        risk_policy(),
        state(),
        evaluated_at=proposal.as_of - timedelta(seconds=1),
    )

    assert RiskRejectionCode.EXPIRED_PROPOSAL in expired.reason_codes
    assert RiskRejectionCode.STALE_PROPOSAL in stale.reason_codes
    assert RiskRejectionCode.FUTURE_PROPOSAL in future.reason_codes


def test_drawdown_snapshot_blocks_without_fabricating_pnl() -> None:
    proposal = trade_proposal()
    safety = safety_state(agent_loss_breached=True)
    decision = RiskEngine().evaluate(
        proposal,
        risk_policy(),
        state(safety=safety),
        evaluated_at=proposal.as_of,
    )

    assert decision.reason_codes == (RiskRejectionCode.DRAWDOWN_LOCK,)


def test_environment_and_approval_policy_are_independent() -> None:
    paper = trade_proposal(
        environment=ExecutionEnvironment.PAPER,
        approval_policy=ApprovalPolicy.FULL_AUTO,
    )
    allowing_paper = risk_policy(
        allowed_execution_environments=(
            ExecutionEnvironment.PAPER,
            ExecutionEnvironment.SIMULATION,
        )
    )
    approved = RiskEngine().evaluate(paper, allowing_paper, state(), evaluated_at=paper.as_of)
    blocked = RiskEngine().evaluate(paper, risk_policy(), state(), evaluated_at=paper.as_of)

    assert approved.status is RiskDecisionStatus.APPROVED_FOR_RESERVATION
    assert RiskRejectionCode.ENVIRONMENT_RESTRICTION in blocked.reason_codes
    assert (
        paper.authority_context.execution_dimensions.execution_environment
        is ExecutionEnvironment.PAPER
    )
    assert paper.authority_context.execution_dimensions.approval_policy is ApprovalPolicy.FULL_AUTO


def test_signal_only_can_be_risk_evaluated_but_cannot_reserve() -> None:
    proposal = trade_proposal(
        submission_mode=SubmissionMode.SIGNAL_ONLY,
        approval_policy=ApprovalPolicy.FULL_AUTO,
    )
    configured = risk_policy()
    engine = RiskEngine()
    preflight = engine.evaluate(proposal, configured, state(), evaluated_at=proposal.as_of)
    final = engine.evaluate_for_reservation(
        proposal,
        configured,
        state(),
        evaluated_at=proposal.as_of,
        approval_binding=None,
    )

    assert preflight.status is RiskDecisionStatus.APPROVED_FOR_RESERVATION
    assert final.reason_codes == (RiskRejectionCode.SUBMISSION_NOT_ENABLED,)


def test_monetary_risk_cap_can_only_reduce_sized_quantity() -> None:
    proposal = trade_proposal()
    uncapped = RiskEngine().evaluate(proposal, risk_policy(), state(), evaluated_at=proposal.as_of)
    capped = RiskEngine().evaluate(
        proposal,
        risk_policy(max_monetary_risk=Decimal("0.25"), quantity_increment=Decimal("0.0001")),
        state(),
        evaluated_at=proposal.as_of,
    )

    assert uncapped.sizing_decision is not None
    assert capped.sizing_decision is not None
    assert capped.sizing_decision.quantity < uncapped.sizing_decision.quantity
    assert capped.sizing_decision.modeled_risk_amount <= Decimal("0.25")


def test_maximum_active_reservation_count_blocks_preflight() -> None:
    proposal = trade_proposal()
    allocation = allocation_snapshot().model_copy(update={"active_reservation_count": 1})
    decision = RiskEngine().evaluate(
        proposal,
        risk_policy(max_concurrent_reservations=1),
        state(allocation=allocation),
        evaluated_at=proposal.as_of,
    )

    assert decision.reason_codes == (RiskRejectionCode.RESERVATION_CAPACITY_UNAVAILABLE,)


@pytest.mark.parametrize("capital", ["50", "100", "250", "500", "1000"])
def test_sizing_scales_across_configured_capital_without_hardcoded_eur50(
    capital: str,
) -> None:
    proposal = trade_proposal()
    snapshot = state(
        parent=parent_snapshot(capital), allocation=allocation_snapshot(capital=capital)
    )
    decision = RiskEngine().evaluate(
        proposal,
        risk_policy(max_risk_fraction=Decimal("0.01"), quantity_increment=Decimal("0.0001")),
        snapshot,
        evaluated_at=proposal.as_of,
    )

    assert decision.status is RiskDecisionStatus.APPROVED_FOR_RESERVATION
    assert decision.sizing_decision is not None
    assert decision.sizing_decision.allowed_risk_amount == Decimal(capital) * Decimal("0.01")


@pytest.mark.parametrize("stop", ["104.9", "103", "100"])
def test_varied_stop_distance_never_exceeds_risk_budget(stop: str) -> None:
    original = trade_proposal()
    content = original.model_dump(mode="python", exclude={"proposal_id"})
    content["stop_level"] = Decimal(stop)
    proposal = TradeProposal(
        proposal_id=calculate_trade_proposal_id(content),
        **content,
    )
    decision = RiskEngine().evaluate(
        proposal,
        risk_policy(max_risk_fraction=Decimal("0.01"), quantity_increment=Decimal("0.0001")),
        state(),
        evaluated_at=proposal.as_of,
    )

    assert decision.sizing_decision is not None
    assert (
        decision.sizing_decision.modeled_risk_amount <= decision.sizing_decision.allowed_risk_amount
    )
