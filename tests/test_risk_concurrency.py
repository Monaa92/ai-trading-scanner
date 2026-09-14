from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

from risk_helpers import (
    ACCOUNT_ID,
    allocation_snapshot,
    coordinator,
    parent_snapshot,
    risk_policy,
    trade_proposal,
)

from ai_trading_scanner.domain import AllocationId
from ai_trading_scanner.risk import (
    CapitalReservation,
    InMemoryCapitalCoordinator,
    ReservationAttempt,
    ReservationAttemptStatus,
    ReservationState,
    RiskConfiguration,
    RiskDecision,
    RiskEngine,
    SafetyLockReason,
    SafetyLockScope,
    create_safety_lock,
)
from ai_trading_scanner.strategies import TradeProposal


def _reserve_at_barrier(
    barrier: Barrier,
    store: InMemoryCapitalCoordinator,
    proposal: TradeProposal,
    configured: RiskConfiguration,
    preliminary: RiskDecision,
    allocation_id: AllocationId,
) -> ReservationAttempt:
    barrier.wait()
    return store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=allocation_id,
        evaluated_at=proposal.as_of,
    )


def test_same_agent_concurrent_requests_cannot_overreserve() -> None:
    configured = risk_policy(max_concurrent_reservations=2)
    allocation_id = AllocationId.parse("allocation:A")
    store = coordinator()
    first_proposal = trade_proposal(final_quantity=Decimal("0.7"))
    second_proposal = trade_proposal(final_quantity=Decimal("0.7"), validity_extension_minutes=1)
    initial = store.evaluation_state(ACCOUNT_ID, allocation_id)
    engine = RiskEngine()
    first_decision = engine.evaluate(
        first_proposal, configured, initial, evaluated_at=first_proposal.as_of
    )
    second_decision = engine.evaluate(
        second_proposal, configured, initial, evaluated_at=second_proposal.as_of
    )
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = (
            pool.submit(
                _reserve_at_barrier,
                barrier,
                store,
                first_proposal,
                configured,
                first_decision,
                allocation_id,
            ),
            pool.submit(
                _reserve_at_barrier,
                barrier,
                store,
                second_proposal,
                configured,
                second_decision,
                allocation_id,
            ),
        )
        results = tuple(future.result() for future in futures)

    assert sorted(result.status.value for result in results) == ["REJECTED", "RESERVED"]
    parent = store.parent_snapshot(ACCOUNT_ID)
    allocation = store.allocation_snapshot(allocation_id)
    assert parent.available_capital >= 0
    assert allocation.available_capital >= 0
    assert parent.total_capital == (
        parent.available_capital + parent.active_reserved_capital + parent.committed_capital
    )
    assert allocation.active_reservation_count == 1


def test_different_agents_cannot_exceed_shared_parent_capacity() -> None:
    configured = risk_policy(max_concurrent_reservations=2)
    allocation_a = allocation_snapshot(agent="agent:A", allocation="allocation:A")
    allocation_b = allocation_snapshot(agent="agent:B", allocation="allocation:B")
    store = coordinator(parent=parent_snapshot("100"), allocations=(allocation_a, allocation_b))
    proposal_a = trade_proposal(agent="agent:A", final_quantity=Decimal("0.7"))
    proposal_b = trade_proposal(agent="agent:B", final_quantity=Decimal("0.7"))
    engine = RiskEngine()
    decision_a = engine.evaluate(
        proposal_a,
        configured,
        store.evaluation_state(ACCOUNT_ID, allocation_a.allocation_id),
        evaluated_at=proposal_a.as_of,
    )
    decision_b = engine.evaluate(
        proposal_b,
        configured,
        store.evaluation_state(ACCOUNT_ID, allocation_b.allocation_id),
        evaluated_at=proposal_b.as_of,
    )
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = (
            pool.submit(
                _reserve_at_barrier,
                barrier,
                store,
                proposal_a,
                configured,
                decision_a,
                allocation_a.allocation_id,
            ),
            pool.submit(
                _reserve_at_barrier,
                barrier,
                store,
                proposal_b,
                configured,
                decision_b,
                allocation_b.allocation_id,
            ),
        )
        attempts = tuple(future.result() for future in results)

    assert sorted(item.status.value for item in attempts) == ["REJECTED", "RESERVED"]
    parent = store.parent_snapshot(ACCOUNT_ID)
    assert parent.active_reserved_capital <= parent.total_capital
    assert (
        sum(
            store.allocation_snapshot(item.allocation_id).active_reserved_capital
            for item in (allocation_a, allocation_b)
        )
        == parent.active_reserved_capital
    )


def test_concurrent_duplicate_proposal_creates_one_reservation() -> None:
    configured = risk_policy()
    allocation_id = AllocationId.parse("allocation:A")
    store = coordinator()
    proposal = trade_proposal(final_quantity=Decimal("0.7"))
    preliminary = RiskEngine().evaluate(
        proposal,
        configured,
        store.evaluation_state(ACCOUNT_ID, allocation_id),
        evaluated_at=proposal.as_of,
    )
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = tuple(
            pool.submit(
                _reserve_at_barrier,
                barrier,
                store,
                proposal,
                configured,
                preliminary,
                allocation_id,
            )
            for _ in range(2)
        )
        attempts = tuple(future.result() for future in futures)

    assert all(item.status is ReservationAttemptStatus.RESERVED for item in attempts)
    assert sum(item.idempotent_replay for item in attempts) == 1
    assert attempts[0].reservation == attempts[1].reservation
    assert store.allocation_snapshot(allocation_id).active_reservation_count == 1


def test_release_racing_reserve_preserves_a_valid_conserved_state() -> None:
    configured = risk_policy(max_concurrent_reservations=2)
    allocation_id = AllocationId.parse("allocation:A")
    store = coordinator()
    first = trade_proposal(final_quantity=Decimal("0.7"))
    second = trade_proposal(final_quantity=Decimal("0.7"), validity_extension_minutes=1)
    initial = store.evaluation_state(ACCOUNT_ID, allocation_id)
    engine = RiskEngine()
    first_decision = engine.evaluate(first, configured, initial, evaluated_at=first.as_of)
    second_decision = engine.evaluate(second, configured, initial, evaluated_at=second.as_of)
    first_result = store.reserve(
        first,
        configured,
        first_decision,
        account_id=ACCOUNT_ID,
        allocation_id=allocation_id,
        evaluated_at=first.as_of,
    )
    first_reservation = first_result.reservation
    assert first_reservation is not None
    barrier = Barrier(2)

    def release() -> CapitalReservation:
        barrier.wait()
        return store.release(
            first_reservation.reservation_id,
            account_id=ACCOUNT_ID,
            allocation_id=allocation_id,
            agent_id=first_reservation.agent_id,
            transitioned_at=first_reservation.created_at + timedelta(seconds=1),
        )

    def reserve() -> ReservationAttempt:
        return _reserve_at_barrier(
            barrier,
            store,
            second,
            configured,
            second_decision,
            allocation_id,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        released_future = pool.submit(release)
        reserve_future = pool.submit(reserve)
        released = released_future.result()
        attempted = reserve_future.result()

    assert released.state is ReservationState.RELEASED
    assert attempted.status in {
        ReservationAttemptStatus.RESERVED,
        ReservationAttemptStatus.REJECTED,
    }
    parent = store.parent_snapshot(ACCOUNT_ID)
    allocation = store.allocation_snapshot(allocation_id)
    assert parent.total_capital == (
        parent.available_capital + parent.active_reserved_capital + parent.committed_capital
    )
    assert allocation.allocated_capital == (
        allocation.available_capital
        + allocation.active_reserved_capital
        + allocation.committed_capital
    )


def test_lock_activation_racing_reservation_is_atomic_and_preserves_existing_if_any() -> None:
    configured = risk_policy()
    allocation_id = AllocationId.parse("allocation:A")
    store = coordinator()
    proposal = trade_proposal(final_quantity=Decimal("0.7"))
    preliminary = RiskEngine().evaluate(
        proposal,
        configured,
        store.evaluation_state(ACCOUNT_ID, allocation_id),
        evaluated_at=proposal.as_of,
    )
    lock = create_safety_lock(
        scope=SafetyLockScope.PARENT_ACCOUNT,
        reason=SafetyLockReason.CIRCUIT_BREAKER,
        account_id=ACCOUNT_ID,
        activated_at=proposal.as_of,
    )
    barrier = Barrier(2)

    def activate() -> None:
        barrier.wait()
        store.activate_lock(lock)

    def reserve() -> ReservationAttempt:
        return _reserve_at_barrier(
            barrier,
            store,
            proposal,
            configured,
            preliminary,
            allocation_id,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        lock_future = pool.submit(activate)
        reserve_future = pool.submit(reserve)
        lock_future.result()
        attempted = reserve_future.result()

    parent = store.parent_snapshot(ACCOUNT_ID)
    allocation = store.allocation_snapshot(allocation_id)
    assert store.safety_snapshot(ACCOUNT_ID, allocation_id).active_locks == (lock,)
    assert parent.available_capital >= 0
    assert allocation.available_capital >= 0
    if attempted.status is ReservationAttemptStatus.RESERVED:
        assert attempted.reservation is not None
        assert attempted.reservation.state is ReservationState.ACTIVE
    else:
        assert allocation.active_reservation_count == 0
