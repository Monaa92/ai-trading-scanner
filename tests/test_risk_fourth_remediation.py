from concurrent.futures import ThreadPoolExecutor
from threading import Condition, Event, RLock, Thread, current_thread
from typing import TypeVar

import pytest
from risk_helpers import (
    ACCOUNT_ID,
    allocation_loss_state,
    allocation_snapshot,
    parent_loss_state,
    parent_snapshot,
    risk_policy,
    trade_proposal,
)

from ai_trading_scanner.risk import (
    InMemoryCapitalCoordinator,
    ReservationAttemptStatus,
    RiskEngine,
    UnknownCapitalScopeError,
)

K = TypeVar("K")
V = TypeVar("V")


class _PausingSetDict[K, V](dict[K, V]):
    def __init__(
        self,
        source: dict[K, V],
        target: K,
        entered: Event,
        resume: Event,
        *,
        pause_after_set: bool,
    ) -> None:
        super().__init__(source)
        self._target = target
        self._entered = entered
        self._resume = resume
        self._pause_after_set = pause_after_set

    def __setitem__(self, key: K, value: V) -> None:
        if key == self._target and not self._pause_after_set:
            self._entered.set()
            if not self._resume.wait(timeout=5):
                raise TimeoutError("publication probe was not resumed")
        super().__setitem__(key, value)
        if key == self._target and self._pause_after_set:
            self._entered.set()
            if not self._resume.wait(timeout=5):
                raise TimeoutError("publication probe was not resumed")


class _FailingSetDict[K, V](dict[K, V]):
    def __init__(self, source: dict[K, V], target: K) -> None:
        super().__init__(source)
        self._target = target

    def __setitem__(self, key: K, value: V) -> None:
        if key == self._target:
            raise RuntimeError("injected publication failure")
        super().__setitem__(key, value)


class _ObservedRegistryLock:
    def __init__(self) -> None:
        self._lock = RLock()
        self._condition = Condition()
        self._reader_attempts = 0

    def __enter__(self) -> None:
        if current_thread().name.startswith("scope-reader"):
            with self._condition:
                self._reader_attempts += 1
                self._condition.notify_all()
        self._lock.acquire()

    def __exit__(self, *args: object) -> None:
        self._lock.release()

    def wait_for_reader_attempts(self, count: int) -> bool:
        with self._condition:
            return self._condition.wait_for(
                lambda: self._reader_attempts >= count,
                timeout=5,
            )


@pytest.mark.parametrize("pause_after_set", [False, True])
def test_parent_registration_has_one_atomic_publication_boundary(
    pause_after_set: bool,
) -> None:
    store = InMemoryCapitalCoordinator()
    observed_lock = _ObservedRegistryLock()
    store._registry_lock = observed_lock  # type: ignore[assignment]
    snapshot = parent_snapshot("100")
    entered = Event()
    resume = Event()
    store._parents = _PausingSetDict(
        store._parents,
        snapshot.account_id,
        entered,
        resume,
        pause_after_set=pause_after_set,
    )
    registration_errors: list[BaseException] = []

    def register() -> None:
        try:
            store.register_parent(snapshot, parent_loss_state("100"))
        except BaseException as error:
            registration_errors.append(error)

    registration = Thread(target=register, name="registration")
    registration.start()
    assert entered.wait(timeout=5)

    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="scope-reader") as pool:
        readers = tuple(pool.submit(store.parent_snapshot, snapshot.account_id) for _ in range(8))
        assert observed_lock.wait_for_reader_attempts(8)
        assert all(not reader.done() for reader in readers)
        resume.set()
        assert all(reader.result(timeout=5) == snapshot for reader in readers)

    registration.join(timeout=5)
    assert not registration.is_alive()
    assert registration_errors == []


@pytest.mark.parametrize("pause_after_set", [False, True])
def test_allocation_registration_has_one_atomic_publication_boundary(
    pause_after_set: bool,
) -> None:
    store = InMemoryCapitalCoordinator()
    store.register_parent(parent_snapshot("100"), parent_loss_state("100"))
    observed_lock = _ObservedRegistryLock()
    store._registry_lock = observed_lock  # type: ignore[assignment]
    snapshot = allocation_snapshot(capital="100")
    entered = Event()
    resume = Event()
    store._allocations = _PausingSetDict(
        store._allocations,
        snapshot.allocation_id,
        entered,
        resume,
        pause_after_set=pause_after_set,
    )
    registration_errors: list[BaseException] = []

    def register() -> None:
        try:
            store.register_allocation(
                snapshot,
                allocation_loss_state(
                    allocation_id=snapshot.allocation_id,
                    agent_id=snapshot.agent_id,
                ),
            )
        except BaseException as error:
            registration_errors.append(error)

    registration = Thread(target=register, name="registration")
    registration.start()
    assert entered.wait(timeout=5)

    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="scope-reader") as pool:
        readers = tuple(
            pool.submit(store.allocation_snapshot, snapshot.allocation_id) for _ in range(8)
        )
        assert observed_lock.wait_for_reader_attempts(8)
        assert all(not reader.done() for reader in readers)
        resume.set()
        assert all(reader.result(timeout=5) == snapshot for reader in readers)

    registration.join(timeout=5)
    assert not registration.is_alive()
    assert registration_errors == []


def test_unpublished_scopes_are_consistently_unknown() -> None:
    store = InMemoryCapitalCoordinator()
    with pytest.raises(UnknownCapitalScopeError):
        store.parent_snapshot(ACCOUNT_ID)

    store.register_parent(parent_snapshot(), parent_loss_state())
    allocation = allocation_snapshot()
    with pytest.raises(UnknownCapitalScopeError):
        store.allocation_snapshot(allocation.allocation_id)


def test_failed_parent_publication_rolls_back_every_registry_entry() -> None:
    store = InMemoryCapitalCoordinator()
    snapshot = parent_snapshot()
    store._parents = _FailingSetDict(store._parents, snapshot.account_id)

    with pytest.raises(RuntimeError, match="injected publication failure"):
        store.register_parent(snapshot, parent_loss_state())

    assert snapshot.account_id not in store._parents
    assert snapshot.account_id not in store._parent_locks
    assert snapshot.account_id not in store._parent_loss_states
    assert snapshot.account_id not in store._allocated_capital_by_account
    assert snapshot.account_id not in store._reservations_by_account
    assert snapshot.account_id not in store._safety_locks

    store._parents = dict(store._parents)
    store.register_parent(snapshot, parent_loss_state())
    assert store.parent_snapshot(snapshot.account_id) == snapshot


def test_failed_allocation_publication_rolls_back_every_registry_entry() -> None:
    store = InMemoryCapitalCoordinator()
    store.register_parent(parent_snapshot(), parent_loss_state())
    snapshot = allocation_snapshot()
    store._allocations = _FailingSetDict(
        store._allocations,
        snapshot.allocation_id,
    )

    with pytest.raises(RuntimeError, match="injected publication failure"):
        store.register_allocation(
            snapshot,
            allocation_loss_state(
                allocation_id=snapshot.allocation_id,
                agent_id=snapshot.agent_id,
            ),
        )

    assert snapshot.allocation_id not in store._allocations
    assert snapshot.agent_id not in store._allocation_by_agent
    assert snapshot.allocation_id not in store._allocation_locks
    assert snapshot.allocation_id not in store._allocation_loss_states
    assert store._allocated_capital_by_account[snapshot.account_id] == 0

    store._allocations = dict(store._allocations)
    store.register_allocation(
        snapshot,
        allocation_loss_state(
            allocation_id=snapshot.allocation_id,
            agent_id=snapshot.agent_id,
        ),
    )
    assert store.allocation_snapshot(snapshot.allocation_id) == snapshot


def test_reservation_can_follow_successful_atomic_registration_immediately() -> None:
    store = InMemoryCapitalCoordinator()
    parent = parent_snapshot()
    allocation = allocation_snapshot()
    store.register_parent(parent, parent_loss_state())
    store.register_allocation(
        allocation,
        allocation_loss_state(
            allocation_id=allocation.allocation_id,
            agent_id=allocation.agent_id,
        ),
    )
    proposal = trade_proposal()
    configured = risk_policy()
    preliminary = RiskEngine().evaluate(
        proposal,
        configured,
        store.evaluation_state(parent.account_id, allocation.allocation_id),
        evaluated_at=proposal.as_of,
    )

    attempt = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=parent.account_id,
        allocation_id=allocation.allocation_id,
        evaluated_at=proposal.as_of,
    )

    assert attempt.status is ReservationAttemptStatus.RESERVED
