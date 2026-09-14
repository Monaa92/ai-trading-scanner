from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Condition, Event, RLock, Thread, current_thread
from typing import TypeVar

import pytest
from risk_helpers import ACCOUNT_ID, ALLOCATION_ID, coordinator, risk_policy, trade_proposal

from ai_trading_scanner.risk import (
    CapitalReservation,
    InMemoryCapitalCoordinator,
    ReservationAttempt,
    ReservationAttemptStatus,
    ReservationState,
    ReservationTransitionError,
    RiskConfiguration,
    RiskDecision,
    RiskEngine,
)
from ai_trading_scanner.strategies import TradeProposal

K = TypeVar("K")
V = TypeVar("V")

RESERVE_STAGES = (
    "parent",
    "allocation",
    "account_reservation",
    "global_reservation",
    "risk_decision",
    "proposal_index",
)
LIFECYCLE_STAGES = (
    "parent",
    "allocation",
    "account_reservation",
    "global_reservation",
)


class _FailOnceSetDict[K, V](dict[K, V]):
    def __init__(self, source: dict[K, V], *, fail_after_set: bool) -> None:
        super().__init__(source)
        self._fail_after_set = fail_after_set
        self._failed = False

    def __setitem__(self, key: K, value: V) -> None:
        if self._failed:
            super().__setitem__(key, value)
            return
        self._failed = True
        if not self._fail_after_set:
            raise RuntimeError("injected publication failure before set")
        super().__setitem__(key, value)
        raise RuntimeError("injected publication failure after set")


class _PauseThenFailSetDict[K, V](dict[K, V]):
    def __init__(self, source: dict[K, V], entered: Event, resume: Event) -> None:
        super().__init__(source)
        self._entered = entered
        self._resume = resume
        self._paused = False

    def __setitem__(self, key: K, value: V) -> None:
        super().__setitem__(key, value)
        if not self._paused:
            self._paused = True
            self._entered.set()
            if not self._resume.wait(timeout=5):
                raise TimeoutError("publication probe was not resumed")
            raise RuntimeError("injected publication failure after pause")


class _ObservedRegistryLock:
    def __init__(self, observed_prefix: str) -> None:
        self._lock = RLock()
        self._condition = Condition()
        self._observed_prefix = observed_prefix
        self._attempts = 0

    def __enter__(self) -> None:
        if current_thread().name.startswith(self._observed_prefix):
            with self._condition:
                self._attempts += 1
                self._condition.notify_all()
        self._lock.acquire()

    def __exit__(self, *args: object) -> None:
        self._lock.release()

    def wait_for_attempts(self, count: int) -> bool:
        with self._condition:
            return self._condition.wait_for(lambda: self._attempts >= count, timeout=5)


def _prepared_reservation(
    *, validity_extension_minutes: int = 0
) -> tuple[
    InMemoryCapitalCoordinator,
    TradeProposal,
    RiskConfiguration,
    RiskDecision,
]:
    store = coordinator()
    proposal = trade_proposal(
        final_quantity=Decimal("0.7"),
        validity_extension_minutes=validity_extension_minutes,
    )
    configured = risk_policy(max_concurrent_reservations=2)
    preliminary = RiskEngine().evaluate(
        proposal,
        configured,
        store.evaluation_state(ACCOUNT_ID, ALLOCATION_ID),
        evaluated_at=proposal.as_of,
    )
    return store, proposal, configured, preliminary


def _reserve(
    store: InMemoryCapitalCoordinator,
    proposal: TradeProposal,
    configured: RiskConfiguration,
    preliminary: RiskDecision,
) -> ReservationAttempt:
    return store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=ALLOCATION_ID,
        evaluated_at=proposal.as_of,
    )


def _published_state(store: InMemoryCapitalCoordinator) -> tuple[object, ...]:
    return (
        dict(store._parents),
        dict(store._allocations),
        {
            account_id: dict(reservations)
            for account_id, reservations in store._reservations_by_account.items()
        },
        dict(store._reservations),
        dict(store._risk_decisions),
        dict(store._proposal_reservations),
    )


def _inject_failure(
    store: InMemoryCapitalCoordinator,
    stage: str,
    *,
    fail_after_set: bool,
) -> None:
    if stage == "parent":
        store._parents = _FailOnceSetDict(store._parents, fail_after_set=fail_after_set)
    elif stage == "allocation":
        store._allocations = _FailOnceSetDict(
            store._allocations,
            fail_after_set=fail_after_set,
        )
    elif stage == "account_reservation":
        store._reservations_by_account[ACCOUNT_ID] = _FailOnceSetDict(
            store._reservations_by_account[ACCOUNT_ID],
            fail_after_set=fail_after_set,
        )
    elif stage == "global_reservation":
        store._reservations = _FailOnceSetDict(
            store._reservations,
            fail_after_set=fail_after_set,
        )
    elif stage == "risk_decision":
        store._risk_decisions = _FailOnceSetDict(
            store._risk_decisions,
            fail_after_set=fail_after_set,
        )
    elif stage == "proposal_index":
        store._proposal_reservations = _FailOnceSetDict(
            store._proposal_reservations,
            fail_after_set=fail_after_set,
        )
    else:
        raise AssertionError(f"unknown publication stage: {stage}")


def _assert_conserved(store: InMemoryCapitalCoordinator) -> None:
    parent = store.parent_snapshot(ACCOUNT_ID)
    allocation = store.allocation_snapshot(ALLOCATION_ID)
    assert parent.total_capital == (
        parent.available_capital + parent.active_reserved_capital + parent.committed_capital
    )
    assert allocation.allocated_capital == (
        allocation.available_capital
        + allocation.active_reserved_capital
        + allocation.committed_capital
    )
    assert parent.active_reserved_capital == allocation.active_reserved_capital
    assert parent.committed_capital == allocation.committed_capital


@pytest.mark.parametrize("stage", RESERVE_STAGES)
@pytest.mark.parametrize("fail_after_set", [False, True], ids=["before", "after"])
def test_reserve_publication_failure_rolls_back_every_mutation_and_retry_succeeds(
    stage: str,
    fail_after_set: bool,
) -> None:
    store, proposal, configured, preliminary = _prepared_reservation()
    before = _published_state(store)
    _inject_failure(store, stage, fail_after_set=fail_after_set)

    with pytest.raises(RuntimeError, match="injected publication failure"):
        _reserve(store, proposal, configured, preliminary)

    assert _published_state(store) == before
    _assert_conserved(store)

    result = _reserve(store, proposal, configured, preliminary)
    assert result.status is ReservationAttemptStatus.RESERVED
    assert result.reservation is not None
    replay = _reserve(store, proposal, configured, preliminary)
    assert replay.status is ReservationAttemptStatus.RESERVED
    assert replay.idempotent_replay
    assert replay.reservation == result.reservation
    assert len(store._reservations) == 1
    assert len(store._risk_decisions) == 1
    assert len(store._proposal_reservations) == 1
    _assert_conserved(store)


def _transition(
    store: InMemoryCapitalCoordinator,
    reservation: CapitalReservation,
    target: ReservationState,
) -> CapitalReservation:
    transitioned_at = (
        reservation.expires_at
        if target is ReservationState.EXPIRED
        else reservation.created_at + timedelta(seconds=1)
    )
    method = {
        ReservationState.RELEASED: store.release,
        ReservationState.EXPIRED: store.expire,
        ReservationState.CONSUMED: store.consume,
    }[target]
    return method(
        reservation.reservation_id,
        account_id=reservation.account_id,
        allocation_id=reservation.allocation_id,
        agent_id=reservation.agent_id,
        transitioned_at=transitioned_at,
    )


@pytest.mark.parametrize(
    "target",
    [ReservationState.RELEASED, ReservationState.EXPIRED, ReservationState.CONSUMED],
)
@pytest.mark.parametrize("stage", LIFECYCLE_STAGES)
@pytest.mark.parametrize("fail_after_set", [False, True], ids=["before", "after"])
def test_lifecycle_publication_failure_restores_active_state_and_retry_succeeds(
    target: ReservationState,
    stage: str,
    fail_after_set: bool,
) -> None:
    store, proposal, configured, preliminary = _prepared_reservation()
    attempted = _reserve(store, proposal, configured, preliminary)
    reservation = attempted.reservation
    assert reservation is not None
    before = _published_state(store)
    _inject_failure(store, stage, fail_after_set=fail_after_set)

    with pytest.raises(RuntimeError, match="injected publication failure"):
        _transition(store, reservation, target)

    assert _published_state(store) == before
    assert store.reservation(reservation.reservation_id).state is ReservationState.ACTIVE
    _assert_conserved(store)

    transitioned = _transition(store, reservation, target)
    assert transitioned.state is target
    assert _transition(store, reservation, target) == transitioned
    conflicting = (
        ReservationState.CONSUMED
        if target is not ReservationState.CONSUMED
        else ReservationState.RELEASED
    )
    with pytest.raises(ReservationTransitionError, match="cannot transition"):
        _transition(store, reservation, conflicting)
    assert store.reservation(reservation.reservation_id) == transitioned
    _assert_conserved(store)


def test_concurrent_readers_cannot_observe_intermediate_reservation_publication() -> None:
    store, proposal, configured, preliminary = _prepared_reservation()
    original = store.parent_snapshot(ACCOUNT_ID)
    entered = Event()
    resume = Event()
    observed_lock = _ObservedRegistryLock("publication-reader")
    store._registry_lock = observed_lock  # type: ignore[assignment]
    store._parents = _PauseThenFailSetDict(store._parents, entered, resume)
    errors: list[BaseException] = []

    def publish() -> None:
        try:
            _reserve(store, proposal, configured, preliminary)
        except BaseException as error:
            errors.append(error)

    publisher = Thread(target=publish, name="publisher")
    publisher.start()
    assert entered.wait(timeout=5)

    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="publication-reader") as pool:
        readers = tuple(pool.submit(store.parent_snapshot, ACCOUNT_ID) for _ in range(8))
        assert observed_lock.wait_for_attempts(8)
        assert all(not reader.done() for reader in readers)
        resume.set()
        snapshots = tuple(reader.result(timeout=5) for reader in readers)

    publisher.join(timeout=5)
    assert not publisher.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert all(snapshot == original for snapshot in snapshots)
    assert store.parent_snapshot(ACCOUNT_ID) == original
    assert store._reservations == {}
    _assert_conserved(store)


def test_competing_reservation_cannot_exploit_intermediate_publication() -> None:
    store, first, configured, first_preliminary = _prepared_reservation()
    second = trade_proposal(final_quantity=Decimal("0.7"), validity_extension_minutes=1)
    second_preliminary = RiskEngine().evaluate(
        second,
        configured,
        store.evaluation_state(ACCOUNT_ID, ALLOCATION_ID),
        evaluated_at=second.as_of,
    )
    entered = Event()
    resume = Event()
    observed_lock = _ObservedRegistryLock("competing-reservation")
    store._registry_lock = observed_lock  # type: ignore[assignment]
    store._parents = _PauseThenFailSetDict(store._parents, entered, resume)
    results: list[ReservationAttempt] = []
    errors: list[BaseException] = []
    competitor_done = Event()

    def reserve_first() -> None:
        try:
            results.append(_reserve(store, first, configured, first_preliminary))
        except BaseException as error:
            errors.append(error)

    def reserve_second() -> None:
        try:
            results.append(_reserve(store, second, configured, second_preliminary))
        except BaseException as error:
            errors.append(error)
        finally:
            competitor_done.set()

    publisher = Thread(target=reserve_first, name="publisher")
    competitor = Thread(target=reserve_second, name="competing-reservation")
    publisher.start()
    assert entered.wait(timeout=5)
    competitor.start()
    assert observed_lock.wait_for_attempts(1)
    assert not competitor_done.is_set()
    resume.set()
    publisher.join(timeout=5)
    competitor.join(timeout=5)

    assert not publisher.is_alive()
    assert not competitor.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert len(results) == 1
    assert results[0].status is ReservationAttemptStatus.RESERVED
    assert len(store._reservations) == 1
    assert len(store._proposal_reservations) == 1
    _assert_conserved(store)
