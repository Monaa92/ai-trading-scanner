from datetime import timedelta
from decimal import Decimal

import pytest
from risk_helpers import (
    ACCOUNT_ID,
    allocation_snapshot,
    approval_binding,
    coordinator,
    parent_snapshot,
    risk_policy,
    state,
    trade_proposal,
)

from ai_trading_scanner.domain import AgentId, AllocationId
from ai_trading_scanner.domain.execution import ApprovalPolicy
from ai_trading_scanner.risk import (
    InMemoryCapitalCoordinator,
    ReservationAttempt,
    ReservationAttemptStatus,
    ReservationState,
    ReservationTransitionError,
    RiskConfiguration,
    RiskDecisionStatus,
    RiskEngine,
    RiskRejectionCode,
    SafetyLockReason,
    SafetyLockScope,
    UnknownCapitalScopeError,
    create_safety_lock,
)
from ai_trading_scanner.strategies import TradeProposal


def reserve_once() -> tuple[
    TradeProposal,
    RiskConfiguration,
    InMemoryCapitalCoordinator,
    ReservationAttempt,
]:
    proposal = trade_proposal(
        final_quantity=Decimal("0.7"), approval_policy=ApprovalPolicy.FULL_AUTO
    )
    configured = risk_policy()
    store = coordinator()
    snapshot = store.evaluation_state(ACCOUNT_ID, AllocationId.parse("allocation:A"))
    preliminary = RiskEngine().evaluate(proposal, configured, snapshot, evaluated_at=proposal.as_of)
    result = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=AllocationId.parse("allocation:A"),
        evaluated_at=proposal.as_of,
    )
    return proposal, configured, store, result


def test_successful_reservation_updates_both_scopes_and_conserves_capital() -> None:
    _, _, store, result = reserve_once()

    assert result.status is ReservationAttemptStatus.RESERVED
    assert result.reservation is not None
    amount = result.reservation.reserved_amount
    parent = store.parent_snapshot(ACCOUNT_ID)
    allocation = store.allocation_snapshot(AllocationId.parse("allocation:A"))
    assert parent.available_capital == Decimal("100") - amount
    assert allocation.available_capital == Decimal("100") - amount
    assert parent.total_capital == parent.available_capital + parent.active_reserved_capital
    assert allocation.allocated_capital == (
        allocation.available_capital + allocation.active_reserved_capital
    )


def test_release_is_idempotent_and_restores_exact_capacity() -> None:
    _, _, store, result = reserve_once()
    reservation = result.reservation
    assert reservation is not None
    at = reservation.created_at + timedelta(seconds=1)

    released = store.release(
        reservation.reservation_id,
        account_id=reservation.account_id,
        allocation_id=reservation.allocation_id,
        agent_id=reservation.agent_id,
        transitioned_at=at,
    )
    repeated = store.release(
        reservation.reservation_id,
        account_id=reservation.account_id,
        allocation_id=reservation.allocation_id,
        agent_id=reservation.agent_id,
        transitioned_at=at + timedelta(seconds=1),
    )

    assert released.state is ReservationState.RELEASED
    assert repeated == released
    assert store.parent_snapshot(ACCOUNT_ID).available_capital == Decimal("100")
    assert store.allocation_snapshot(reservation.allocation_id).available_capital == Decimal("100")


def test_consume_moves_reserved_capital_to_committed_without_restoring_available() -> None:
    _, _, store, result = reserve_once()
    reservation = result.reservation
    assert reservation is not None
    before_available = store.parent_snapshot(ACCOUNT_ID).available_capital

    consumed = store.consume(
        reservation.reservation_id,
        account_id=reservation.account_id,
        allocation_id=reservation.allocation_id,
        agent_id=reservation.agent_id,
        transitioned_at=reservation.created_at + timedelta(seconds=1),
    )

    parent = store.parent_snapshot(ACCOUNT_ID)
    allocation = store.allocation_snapshot(reservation.allocation_id)
    assert consumed.state is ReservationState.CONSUMED
    assert parent.available_capital == before_available
    assert parent.active_reserved_capital == 0
    assert parent.committed_capital == reservation.reserved_amount
    assert allocation.instrument_committed_capital == reservation.reserved_amount


def test_expiry_requires_deadline_and_restores_capacity() -> None:
    _, _, store, result = reserve_once()
    reservation = result.reservation
    assert reservation is not None
    with pytest.raises(ReservationTransitionError, match="has not expired"):
        store.expire(
            reservation.reservation_id,
            account_id=reservation.account_id,
            allocation_id=reservation.allocation_id,
            agent_id=reservation.agent_id,
            transitioned_at=reservation.created_at,
        )
    expired = store.expire(
        reservation.reservation_id,
        account_id=reservation.account_id,
        allocation_id=reservation.allocation_id,
        agent_id=reservation.agent_id,
        transitioned_at=reservation.expires_at,
    )

    assert expired.state is ReservationState.EXPIRED
    assert store.parent_snapshot(ACCOUNT_ID).available_capital == Decimal("100")


def test_conflicting_terminal_transition_and_wrong_owner_change_nothing() -> None:
    _, _, store, result = reserve_once()
    reservation = result.reservation
    assert reservation is not None
    before_parent = store.parent_snapshot(ACCOUNT_ID)
    before_allocation = store.allocation_snapshot(reservation.allocation_id)
    with pytest.raises(ReservationTransitionError, match="ownership mismatch"):
        store.release(
            reservation.reservation_id,
            account_id=reservation.account_id,
            allocation_id=reservation.allocation_id,
            agent_id=AgentId.parse("agent:B"),
            transitioned_at=reservation.created_at + timedelta(seconds=1),
        )
    assert store.parent_snapshot(ACCOUNT_ID) == before_parent
    assert store.allocation_snapshot(reservation.allocation_id) == before_allocation

    store.release(
        reservation.reservation_id,
        account_id=reservation.account_id,
        allocation_id=reservation.allocation_id,
        agent_id=reservation.agent_id,
        transitioned_at=reservation.created_at + timedelta(seconds=1),
    )
    with pytest.raises(ReservationTransitionError, match="cannot transition"):
        store.consume(
            reservation.reservation_id,
            account_id=reservation.account_id,
            allocation_id=reservation.allocation_id,
            agent_id=reservation.agent_id,
            transitioned_at=reservation.created_at + timedelta(seconds=2),
        )


def test_same_active_proposal_returns_existing_reservation_idempotently() -> None:
    proposal, configured, store, first = reserve_once()
    replay = store.reserve(
        proposal,
        configured,
        first.risk_decision,
        account_id=ACCOUNT_ID,
        allocation_id=AllocationId.parse("allocation:A"),
        evaluated_at=proposal.as_of,
    )

    assert replay.status is ReservationAttemptStatus.RESERVED
    assert replay.idempotent_replay is True
    assert replay.reservation == first.reservation
    allocation = store.allocation_snapshot(AllocationId.parse("allocation:A"))
    assert allocation.active_reservation_count == 1


def test_active_replay_rejects_a_different_preliminary_risk_decision() -> None:
    proposal, configured, store, first = reserve_once()
    different_decision = RiskEngine().evaluate(
        proposal,
        configured,
        state(),
        evaluated_at=proposal.as_of + timedelta(seconds=1),
    )
    replay = store.reserve(
        proposal,
        configured,
        different_decision,
        account_id=ACCOUNT_ID,
        allocation_id=AllocationId.parse("allocation:A"),
        evaluated_at=proposal.as_of + timedelta(seconds=1),
    )

    assert replay.status is ReservationAttemptStatus.REJECTED
    assert replay.risk_decision.reason_codes == (RiskRejectionCode.PRELIMINARY_DECISION_MISMATCH,)
    assert (
        store.allocation_snapshot(AllocationId.parse("allocation:A")).active_reservation_count == 1
    )


def test_terminal_proposal_cannot_create_a_new_reservation() -> None:
    proposal, configured, store, first = reserve_once()
    reservation = first.reservation
    assert reservation is not None
    store.release(
        reservation.reservation_id,
        account_id=reservation.account_id,
        allocation_id=reservation.allocation_id,
        agent_id=reservation.agent_id,
        transitioned_at=reservation.created_at + timedelta(seconds=1),
    )
    replay = store.reserve(
        proposal,
        configured,
        first.risk_decision,
        account_id=ACCOUNT_ID,
        allocation_id=reservation.allocation_id,
        evaluated_at=proposal.as_of,
    )

    assert replay.status is ReservationAttemptStatus.REJECTED
    assert replay.risk_decision.reason_codes == (RiskRejectionCode.DUPLICATE_TERMINAL_RESERVATION,)


def test_manual_policy_requires_exact_external_approval_binding() -> None:
    proposal = trade_proposal(
        final_quantity=Decimal("0.7"), approval_policy=ApprovalPolicy.MANUAL_APPROVAL
    )
    configured = risk_policy()
    store = coordinator()
    snapshot = store.evaluation_state(ACCOUNT_ID, AllocationId.parse("allocation:A"))
    preliminary = RiskEngine().evaluate(proposal, configured, snapshot, evaluated_at=proposal.as_of)
    missing = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=AllocationId.parse("allocation:A"),
        evaluated_at=proposal.as_of,
    )
    binding = approval_binding(proposal, snapshot, configured)
    accepted = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=AllocationId.parse("allocation:A"),
        evaluated_at=proposal.as_of,
        approval_binding=binding,
    )

    assert missing.risk_decision.reason_codes == (RiskRejectionCode.APPROVAL_REQUIRED,)
    assert accepted.status is ReservationAttemptStatus.RESERVED
    assert accepted.reservation is not None
    assert accepted.reservation.approval_binding_id == binding.approval_binding_id


def test_manual_reservation_requires_final_quantity_in_immutable_proposal() -> None:
    proposal = trade_proposal(approval_policy=ApprovalPolicy.MANUAL_APPROVAL)
    configured = risk_policy()
    store = coordinator()
    snapshot = store.evaluation_state(ACCOUNT_ID, AllocationId.parse("allocation:A"))
    preliminary = RiskEngine().evaluate(proposal, configured, snapshot, evaluated_at=proposal.as_of)
    binding = approval_binding(proposal, snapshot, configured)

    attempt = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=AllocationId.parse("allocation:A"),
        evaluated_at=proposal.as_of,
        approval_binding=binding,
    )

    assert attempt.risk_decision.reason_codes == (RiskRejectionCode.APPROVAL_CONTEXT_MISMATCH,)


def test_full_auto_rejects_unexpected_manual_approval_binding() -> None:
    proposal = trade_proposal(final_quantity=Decimal("0.7"))
    configured = risk_policy()
    store = coordinator()
    snapshot = store.evaluation_state(ACCOUNT_ID, AllocationId.parse("allocation:A"))
    preliminary = RiskEngine().evaluate(proposal, configured, snapshot, evaluated_at=proposal.as_of)
    binding = approval_binding(proposal, snapshot, configured)

    attempt = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=AllocationId.parse("allocation:A"),
        evaluated_at=proposal.as_of,
        approval_binding=binding,
    )

    assert attempt.risk_decision.reason_codes == (RiskRejectionCode.APPROVAL_POLICY_MISMATCH,)


def test_unknown_allocation_fails_closed_without_parent_mutation() -> None:
    store = coordinator()
    before = store.parent_snapshot(ACCOUNT_ID)
    with pytest.raises(UnknownCapitalScopeError):
        store.evaluation_state(ACCOUNT_ID, AllocationId.parse("allocation:unknown"))
    assert store.parent_snapshot(ACCOUNT_ID) == before


def test_changed_proposal_cannot_reuse_prior_decision_or_approval() -> None:
    original = trade_proposal(
        final_quantity=Decimal("0.7"), approval_policy=ApprovalPolicy.MANUAL_APPROVAL
    )
    changed = trade_proposal(
        final_quantity=Decimal("0.6"), approval_policy=ApprovalPolicy.MANUAL_APPROVAL
    )
    configured = risk_policy()
    store = coordinator()
    snapshot = store.evaluation_state(ACCOUNT_ID, AllocationId.parse("allocation:A"))
    original_decision = RiskEngine().evaluate(
        original, configured, snapshot, evaluated_at=original.as_of
    )
    original_binding = approval_binding(original, snapshot, configured)

    stale_decision = store.reserve(
        changed,
        configured,
        original_decision,
        account_id=ACCOUNT_ID,
        allocation_id=AllocationId.parse("allocation:A"),
        evaluated_at=changed.as_of,
        approval_binding=original_binding,
    )
    changed_decision = RiskEngine().evaluate(
        changed, configured, snapshot, evaluated_at=changed.as_of
    )
    stale_approval = store.reserve(
        changed,
        configured,
        changed_decision,
        account_id=ACCOUNT_ID,
        allocation_id=AllocationId.parse("allocation:A"),
        evaluated_at=changed.as_of,
        approval_binding=original_binding,
    )

    assert stale_decision.risk_decision.reason_codes == (
        RiskRejectionCode.PRELIMINARY_DECISION_MISMATCH,
    )
    assert stale_approval.risk_decision.reason_codes == (
        RiskRejectionCode.APPROVAL_CONTEXT_MISMATCH,
    )
    assert store.parent_snapshot(ACCOUNT_ID).available_capital == Decimal("100")


def test_active_lock_blocks_new_reservation_without_destroying_existing() -> None:
    _, _, store, first = reserve_once()
    reservation = first.reservation
    assert reservation is not None
    lock = create_safety_lock(
        scope=SafetyLockScope.PARENT_ACCOUNT,
        reason=SafetyLockReason.CIRCUIT_BREAKER,
        account_id=ACCOUNT_ID,
        activated_at=reservation.created_at,
    )
    store.activate_lock(lock)
    second_proposal = trade_proposal(final_quantity=Decimal("0.1"), validity_extension_minutes=1)
    configured = risk_policy(max_concurrent_reservations=2)
    snapshot = store.evaluation_state(ACCOUNT_ID, reservation.allocation_id)
    blocked = RiskEngine().evaluate(
        second_proposal, configured, snapshot, evaluated_at=second_proposal.as_of
    )

    assert blocked.reason_codes == (RiskRejectionCode.TRADING_LOCK,)
    assert store.reservation(reservation.reservation_id).state is ReservationState.ACTIVE


def test_failed_final_revalidation_leaves_both_scopes_unchanged() -> None:
    proposal = trade_proposal(final_quantity=Decimal("0.7"))
    configured = risk_policy()
    store = coordinator(parent=parent_snapshot("50"))
    stale_state = state()
    preliminary = RiskEngine().evaluate(
        proposal, configured, stale_state, evaluated_at=proposal.as_of
    )
    before_parent = store.parent_snapshot(ACCOUNT_ID)
    before_allocation = store.allocation_snapshot(AllocationId.parse("allocation:A"))

    attempt = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=AllocationId.parse("allocation:A"),
        evaluated_at=proposal.as_of,
    )

    assert attempt.status is ReservationAttemptStatus.REJECTED
    assert RiskRejectionCode.INSUFFICIENT_AVAILABLE_CAPITAL in (attempt.risk_decision.reason_codes)
    assert store.parent_snapshot(ACCOUNT_ID) == before_parent
    assert store.allocation_snapshot(AllocationId.parse("allocation:A")) == before_allocation


def test_reservation_identity_binds_material_contract_and_survives_lifecycle_state() -> None:
    _, _, store, result = reserve_once()
    reservation = result.reservation
    assert reservation is not None
    released = store.release(
        reservation.reservation_id,
        account_id=reservation.account_id,
        allocation_id=reservation.allocation_id,
        agent_id=reservation.agent_id,
        transitioned_at=reservation.created_at + timedelta(seconds=1),
    )

    assert released.reservation_id == reservation.reservation_id
    assert released.state is ReservationState.RELEASED


def test_allocation_lock_is_local_while_parent_lock_propagates() -> None:
    allocation_a = allocation_snapshot(agent="agent:A", allocation="allocation:A")
    allocation_b = allocation_snapshot(agent="agent:B", allocation="allocation:B")
    store = coordinator(allocations=(allocation_a, allocation_b))
    local_lock = create_safety_lock(
        scope=SafetyLockScope.AGENT,
        reason=SafetyLockReason.TRADING_LOCK,
        account_id=ACCOUNT_ID,
        allocation_id=allocation_a.allocation_id,
        agent_id=allocation_a.agent_id,
        activated_at=trade_proposal().as_of,
    )
    store.activate_lock(local_lock)

    assert store.safety_snapshot(ACCOUNT_ID, allocation_a.allocation_id).active_locks == (
        local_lock,
    )
    assert store.safety_snapshot(ACCOUNT_ID, allocation_b.allocation_id).active_locks == ()


def test_no_capital_is_held_by_risk_preflight_alone() -> None:
    proposal = trade_proposal(final_quantity=Decimal("0.7"))
    configured = risk_policy()
    store = coordinator()
    before = store.evaluation_state(ACCOUNT_ID, AllocationId.parse("allocation:A"))

    decision = RiskEngine().evaluate(proposal, configured, before, evaluated_at=proposal.as_of)

    assert decision.status is RiskDecisionStatus.APPROVED_FOR_RESERVATION
    assert store.evaluation_state(ACCOUNT_ID, AllocationId.parse("allocation:A")) == before
