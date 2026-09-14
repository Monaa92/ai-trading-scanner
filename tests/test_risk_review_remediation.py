from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from pydantic import ValidationError
from risk_helpers import (
    ACCOUNT_ID,
    allocation_loss_state,
    allocation_snapshot,
    coordinator,
    loss_state,
    parent_loss_state,
    parent_snapshot,
    risk_policy,
    safety_state,
    state,
    trade_proposal,
)

from ai_trading_scanner.domain import AccountId, AllocationId
from ai_trading_scanner.risk import (
    CapitalReservation,
    DuplicateCapitalScopeError,
    InMemoryCapitalCoordinator,
    ReservationAttemptStatus,
    ReservationState,
    ReservationTransitionError,
    RiskConfiguration,
    RiskDecision,
    RiskDecisionStatus,
    RiskEngine,
    RiskEvaluatedLimits,
    RiskRejectionCode,
    SafetyLockReason,
    SafetyLockScope,
    SizingDecision,
    calculate_sizing_decision_id,
    create_loss_state,
    create_safety_lock,
    create_safety_state,
)
from ai_trading_scanner.strategies import TradeProposal

ALLOCATION_A = AllocationId.parse("allocation:A")


def _reserve_once() -> tuple[
    TradeProposal,
    RiskConfiguration,
    InMemoryCapitalCoordinator,
    RiskDecision,
    CapitalReservation,
]:
    proposal = trade_proposal()
    configured = risk_policy(
        max_risk_fraction=Decimal("0.01"),
        max_agent_drawdown_fraction=Decimal("0.015"),
        max_parent_drawdown_fraction=Decimal("0.015"),
        quantity_increment=Decimal("0.0001"),
    )
    store = coordinator()
    preliminary = RiskEngine().evaluate(
        proposal,
        configured,
        store.evaluation_state(ACCOUNT_ID, ALLOCATION_A),
        evaluated_at=proposal.as_of,
    )
    result = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=ALLOCATION_A,
        evaluated_at=proposal.as_of,
    )
    assert result.status is ReservationAttemptStatus.RESERVED
    assert result.reservation is not None
    return proposal, configured, store, preliminary, result.reservation


def test_daily_loss_headroom_just_below_ceiling_constrains_sizing() -> None:
    configured = risk_policy(
        max_risk_fraction=Decimal("1"),
        max_agent_drawdown_fraction=Decimal("0.25"),
        max_parent_drawdown_fraction=Decimal("0.25"),
        quantity_increment=Decimal("0.0001"),
    )
    snapshot = state(safety=safety_state(agent_current_loss="19.9", parent_current_loss="19.9"))
    decision = RiskEngine().evaluate(
        trade_proposal(), configured, snapshot, evaluated_at=trade_proposal().as_of
    )

    assert decision.status is RiskDecisionStatus.APPROVED_FOR_RESERVATION
    assert decision.sizing_decision is not None
    assert decision.evaluated_limits.agent_remaining_loss_headroom == Decimal("0.125")
    assert decision.sizing_decision.modeled_risk_amount <= Decimal("0.125")


def test_exact_daily_loss_ceiling_fails_closed() -> None:
    proposal = trade_proposal()
    configured = risk_policy(
        max_agent_drawdown_fraction=Decimal("0.25"),
        max_parent_drawdown_fraction=Decimal("0.25"),
    )
    decision = RiskEngine().evaluate(
        proposal,
        configured,
        state(safety=safety_state(agent_current_loss="20", parent_current_loss="20")),
        evaluated_at=proposal.as_of,
    )

    assert decision.reason_codes == (RiskRejectionCode.DRAWDOWN_LOCK,)
    assert decision.evaluated_limits.agent_remaining_loss_headroom == 0


def test_outstanding_downside_can_exhaust_remaining_headroom() -> None:
    proposal = trade_proposal()
    base = safety_state(agent_current_loss="19.9", parent_current_loss="19.9")
    constrained = create_safety_state(
        agent_loss_state=base.agent_loss_state,
        parent_loss_state=base.parent_loss_state,
        agent_outstanding_downside=Decimal("0.2"),
        parent_outstanding_downside=Decimal("0.2"),
    )
    decision = RiskEngine().evaluate(
        proposal,
        risk_policy(
            max_agent_drawdown_fraction=Decimal("0.25"),
            max_parent_drawdown_fraction=Decimal("0.25"),
        ),
        state(safety=constrained),
        evaluated_at=proposal.as_of,
    )

    assert decision.reason_codes == (RiskRejectionCode.DRAWDOWN_LOCK,)


def test_loss_state_change_after_preflight_is_revalidated_at_reservation() -> None:
    proposal = trade_proposal(final_quantity=Decimal("0.7"))
    configured = risk_policy(
        max_agent_drawdown_fraction=Decimal("0.25"),
        max_parent_drawdown_fraction=Decimal("0.25"),
    )
    store = coordinator()
    preliminary = RiskEngine().evaluate(
        proposal,
        configured,
        store.evaluation_state(ACCOUNT_ID, ALLOCATION_A),
        evaluated_at=proposal.as_of,
    )
    store.update_allocation_loss_state(
        ALLOCATION_A, loss_state("100", current_loss="19.9", revision=1)
    )
    store.update_parent_loss_state(
        ACCOUNT_ID, parent_loss_state("100", current_loss="19.9", revision=1)
    )

    attempt = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=ALLOCATION_A,
        evaluated_at=proposal.as_of,
    )

    assert attempt.status is ReservationAttemptStatus.REJECTED
    assert RiskRejectionCode.RISK_PER_TRADE_EXCEEDED in attempt.risk_decision.reason_codes
    assert attempt.risk_decision.evaluated_safety_state.agent_loss_state.revision == 1


def test_active_reservation_consumes_downside_budget_for_next_proposal() -> None:
    _, configured, store, _, reservation = _reserve_once()
    second = trade_proposal(final_quantity=Decimal("0.1"), validity_extension_minutes=1)
    current = store.evaluation_state(ACCOUNT_ID, ALLOCATION_A)
    assert current.safety.agent_outstanding_downside == reservation.reserved_downside
    preliminary = RiskEngine().evaluate(second, configured, current, evaluated_at=second.as_of)

    assert preliminary.status is RiskDecisionStatus.REJECTED
    assert RiskRejectionCode.RISK_PER_TRADE_EXCEEDED in preliminary.reason_codes


def test_release_restores_reserved_downside_headroom() -> None:
    _, _, store, _, reservation = _reserve_once()
    store.release(
        reservation.reservation_id,
        account_id=ACCOUNT_ID,
        allocation_id=ALLOCATION_A,
        agent_id=reservation.agent_id,
        transitioned_at=reservation.created_at + timedelta(seconds=1),
    )

    safety = store.safety_snapshot(ACCOUNT_ID, ALLOCATION_A)
    assert safety.agent_outstanding_downside == 0
    assert safety.parent_outstanding_downside == 0


def test_consumed_placeholder_conservatively_retains_modeled_downside() -> None:
    _, _, store, _, reservation = _reserve_once()
    store.consume(
        reservation.reservation_id,
        account_id=ACCOUNT_ID,
        allocation_id=ALLOCATION_A,
        agent_id=reservation.agent_id,
        transitioned_at=reservation.created_at + timedelta(seconds=1),
    )

    safety = store.safety_snapshot(ACCOUNT_ID, ALLOCATION_A)
    assert safety.agent_outstanding_downside == reservation.reserved_downside
    assert safety.parent_outstanding_downside == reservation.reserved_downside


def test_same_agent_cannot_register_second_allocation() -> None:
    second_allocation = allocation_snapshot(allocation="allocation:A2")
    store = coordinator()

    with pytest.raises(DuplicateCapitalScopeError, match="already has an active allocation"):
        store.register_allocation(
            second_allocation,
            allocation_loss_state(allocation_id=second_allocation.allocation_id),
        )


def test_same_proposal_cannot_reserve_across_parent_accounts() -> None:
    store = coordinator()
    other_account = AccountId.parse("account:other")
    other_parent = parent_snapshot().model_copy(update={"account_id": other_account})
    other_allocation = allocation_snapshot(allocation="allocation:other").model_copy(
        update={"account_id": other_account}
    )
    store.register_parent(other_parent, parent_loss_state(account_id=other_account))
    with pytest.raises(DuplicateCapitalScopeError, match="already has an active allocation"):
        store.register_allocation(
            other_allocation,
            allocation_loss_state(
                account_id=other_account,
                allocation_id=other_allocation.allocation_id,
                agent_id=other_allocation.agent_id,
            ),
        )


def test_concurrent_same_agent_allocation_registration_accepts_one() -> None:
    store = InMemoryCapitalCoordinator()
    store.register_parent(parent_snapshot(), parent_loss_state())
    allocations = (
        allocation_snapshot(allocation="allocation:A1"),
        allocation_snapshot(allocation="allocation:A2"),
    )
    barrier = Barrier(2)

    def register(index: int) -> str:
        barrier.wait()
        allocation = allocations[index]
        try:
            store.register_allocation(
                allocation,
                allocation_loss_state(allocation_id=allocation.allocation_id),
            )
        except DuplicateCapitalScopeError:
            return "REJECTED"
        return "REGISTERED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(register, range(2)))

    assert sorted(results) == ["REGISTERED", "REJECTED"]


def test_active_replay_is_valid_just_before_deadline() -> None:
    proposal, configured, store, preliminary, _ = _reserve_once()
    replay = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=ALLOCATION_A,
        evaluated_at=proposal.valid_until - timedelta(microseconds=1),
    )

    assert replay.status is ReservationAttemptStatus.RESERVED
    assert replay.idempotent_replay is True


@pytest.mark.parametrize("offset", [timedelta(0), timedelta(microseconds=1)])
def test_active_replay_at_or_after_deadline_expires_and_rejects(offset: timedelta) -> None:
    proposal, configured, store, preliminary, reservation = _reserve_once()
    replay = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=ALLOCATION_A,
        evaluated_at=proposal.valid_until + offset,
    )

    assert replay.status is ReservationAttemptStatus.REJECTED
    assert replay.risk_decision.reason_codes == (RiskRejectionCode.EXPIRED_PROPOSAL,)
    assert store.reservation(reservation.reservation_id).state is ReservationState.EXPIRED


def test_lock_introduced_before_active_replay_rejects_without_releasing_hold() -> None:
    proposal, configured, store, preliminary, reservation = _reserve_once()
    store.activate_lock(
        create_safety_lock(
            scope=SafetyLockScope.PARENT_ACCOUNT,
            reason=SafetyLockReason.CIRCUIT_BREAKER,
            account_id=ACCOUNT_ID,
            activated_at=proposal.as_of,
        )
    )
    replay = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=ALLOCATION_A,
        evaluated_at=proposal.as_of + timedelta(seconds=1),
    )

    assert replay.risk_decision.reason_codes == (RiskRejectionCode.TRADING_LOCK,)
    assert store.reservation(reservation.reservation_id).state is ReservationState.ACTIVE


def test_consume_at_or_after_expiry_transitions_to_expired_and_fails() -> None:
    proposal, _, store, _, reservation = _reserve_once()
    with pytest.raises(ReservationTransitionError, match="expired reservation"):
        store.consume(
            reservation.reservation_id,
            account_id=ACCOUNT_ID,
            allocation_id=ALLOCATION_A,
            agent_id=reservation.agent_id,
            transitioned_at=proposal.valid_until,
        )

    assert store.reservation(reservation.reservation_id).state is ReservationState.EXPIRED


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("unit_modeled_loss", Decimal("999")),
        ("cash_per_unit", Decimal("999")),
        ("modeled_risk_amount", Decimal("0.0001")),
        ("reservation_amount", Decimal("0.0001")),
        ("round_trip_cost_return", Decimal("0.123")),
    ],
)
def test_sizing_decision_rejects_reidentified_arithmetic_forgery(
    field: str, replacement: Decimal
) -> None:
    proposal = trade_proposal()
    valid = (
        RiskEngine()
        .evaluate(proposal, risk_policy(), state(), evaluated_at=proposal.as_of)
        .sizing_decision
    )
    assert valid is not None
    content = valid.model_dump(mode="python", exclude={"sizing_decision_id"})
    content[field] = replacement
    content["sizing_decision_id"] = calculate_sizing_decision_id(content)

    with pytest.raises(
        ValidationError,
        match=(
            "deterministic result of bound inputs|arithmetically inconsistent|"
            "immutable proposal content"
        ),
    ):
        SizingDecision.model_validate(content)


def test_evaluated_limits_reject_binary_float() -> None:
    proposal = trade_proposal()
    limits = (
        RiskEngine()
        .evaluate(proposal, risk_policy(), state(), evaluated_at=proposal.as_of)
        .evaluated_limits
    )
    content = limits.model_dump(mode="python")
    content["agent_current_loss"] = 0.0

    with pytest.raises(ValidationError, match="must not use float"):
        RiskEvaluatedLimits.model_validate(content)


@pytest.mark.parametrize(
    "field", ["eligible_current_equity", "session_start_equity", "current_loss"]
)
def test_loss_state_rejects_binary_float(field: str) -> None:
    content = loss_state().model_dump(mode="python", exclude={"loss_state_id", "schema_version"})
    content[field] = 1.0

    with pytest.raises(ValidationError, match="must not use float"):
        create_loss_state(**content)


def test_materially_different_loss_states_change_safety_and_decision_identity() -> None:
    proposal = trade_proposal()
    configured = risk_policy()
    first = RiskEngine().evaluate(proposal, configured, state(), evaluated_at=proposal.as_of)
    second = RiskEngine().evaluate(
        proposal,
        configured,
        state(safety=safety_state(agent_current_loss="1", parent_current_loss="1")),
        evaluated_at=proposal.as_of,
    )

    assert first.evaluated_safety_state.safety_state_id != (
        second.evaluated_safety_state.safety_state_id
    )
    assert first.risk_decision_id != second.risk_decision_id


def test_new_loss_state_revision_changes_bound_decision_identity() -> None:
    proposal = trade_proposal()
    configured = risk_policy()
    first = RiskEngine().evaluate(
        proposal, configured, state(safety=safety_state()), evaluated_at=proposal.as_of
    )
    revised = create_safety_state(
        agent_loss_state=loss_state(revision=1),
        parent_loss_state=parent_loss_state(revision=1),
    )
    second = RiskEngine().evaluate(
        proposal, configured, state(safety=revised), evaluated_at=proposal.as_of
    )

    assert first.evaluated_safety_state.safety_state_id != (
        second.evaluated_safety_state.safety_state_id
    )
    assert first.risk_decision_id != second.risk_decision_id


def test_cross_parent_lock_activation_and_evaluation_are_safely_partitioned() -> None:
    store = InMemoryCapitalCoordinator()
    accounts = (AccountId.parse("account:A"), AccountId.parse("account:B"))
    allocations = (
        allocation_snapshot(agent="agent:one", allocation="allocation:one").model_copy(
            update={"account_id": accounts[0]}
        ),
        allocation_snapshot(agent="agent:two", allocation="allocation:two").model_copy(
            update={"account_id": accounts[1]}
        ),
    )
    for account_id, allocation in zip(accounts, allocations, strict=True):
        store.register_parent(
            parent_snapshot().model_copy(update={"account_id": account_id}),
            parent_loss_state(account_id=account_id),
        )
        store.register_allocation(
            allocation,
            allocation_loss_state(
                account_id=account_id,
                allocation_id=allocation.allocation_id,
                agent_id=allocation.agent_id,
            ),
        )
    proposal = trade_proposal()
    barrier = Barrier(2)

    def exercise(index: int) -> None:
        barrier.wait()
        for offset in range(100):
            store.activate_lock(
                create_safety_lock(
                    scope=SafetyLockScope.PARENT_ACCOUNT,
                    reason=SafetyLockReason.TRADING_LOCK,
                    account_id=accounts[index],
                    activated_at=proposal.as_of + timedelta(microseconds=offset),
                )
            )
            store.evaluation_state(accounts[index], allocations[index].allocation_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        tuple(pool.map(exercise, range(2)))

    assert len(store.safety_snapshot(accounts[0], allocations[0].allocation_id).active_locks) == 100
    assert len(store.safety_snapshot(accounts[1], allocations[1].allocation_id).active_locks) == 100
