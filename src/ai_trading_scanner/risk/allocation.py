"""Concurrency-safe in-memory parent and agent capital reservation coordinator."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from threading import RLock

from ai_trading_scanner.domain import (
    AccountId,
    AgentId,
    AllocationId,
    ReservationId,
    SafetyLockId,
    TradeProposalId,
)
from ai_trading_scanner.risk.engine import RiskEngine
from ai_trading_scanner.risk.models import (
    AllocationSnapshot,
    ApprovalBinding,
    CapitalReservation,
    ParentCapitalSnapshot,
    ReservationAttempt,
    ReservationAttemptStatus,
    ReservationState,
    ReservationTransitionError,
    RiskConfiguration,
    RiskDecision,
    RiskDecisionStatus,
    RiskEvaluationState,
    RiskRejectionCode,
    SafetyLock,
    SafetyLockScope,
    SafetyStateSnapshot,
    calculate_reservation_id,
)
from ai_trading_scanner.strategies import TradeProposal


class UnknownCapitalScopeError(LookupError):
    """Raised when an account, allocation, or reservation is not registered."""


class DuplicateCapitalScopeError(ValueError):
    """Raised when a stable account or allocation identity is registered twice."""


class InMemoryCapitalCoordinator:
    """Local transactional boundary with deterministic parent→allocation lock order."""

    def __init__(self, risk_engine: RiskEngine | None = None) -> None:
        self._risk_engine = risk_engine or RiskEngine()
        self._registry_lock = RLock()
        self._parents: dict[AccountId, ParentCapitalSnapshot] = {}
        self._allocations: dict[AllocationId, AllocationSnapshot] = {}
        self._parent_locks: dict[AccountId, RLock] = {}
        self._allocation_locks: dict[AllocationId, RLock] = {}
        self._reservations: dict[ReservationId, CapitalReservation] = {}
        self._proposal_reservations: dict[tuple[AllocationId, TradeProposalId], ReservationId] = {}
        self._safety_locks: dict[SafetyLockId, SafetyLock] = {}

    def register_parent(self, snapshot: ParentCapitalSnapshot) -> None:
        with self._registry_lock:
            if snapshot.account_id in self._parents:
                raise DuplicateCapitalScopeError("parent account is already registered")
            self._parents[snapshot.account_id] = snapshot
            self._parent_locks[snapshot.account_id] = RLock()

    def register_allocation(self, snapshot: AllocationSnapshot) -> None:
        with self._registry_lock:
            if snapshot.account_id not in self._parents:
                raise UnknownCapitalScopeError("parent account is not registered")
            if snapshot.allocation_id in self._allocations:
                raise DuplicateCapitalScopeError("allocation is already registered")
            self._allocations[snapshot.allocation_id] = snapshot
            self._allocation_locks[snapshot.allocation_id] = RLock()

    def parent_snapshot(self, account_id: AccountId) -> ParentCapitalSnapshot:
        with self._parent_lock(account_id):
            return self._parent(account_id)

    def allocation_snapshot(self, allocation_id: AllocationId) -> AllocationSnapshot:
        allocation = self._allocation(allocation_id)
        with self._scope_locks(allocation.account_id, allocation_id):
            return self._allocation(allocation_id)

    def safety_snapshot(
        self, account_id: AccountId, allocation_id: AllocationId
    ) -> SafetyStateSnapshot:
        with self._scope_locks(account_id, allocation_id):
            return self._safety_snapshot(account_id, allocation_id)

    def evaluation_state(
        self, account_id: AccountId, allocation_id: AllocationId
    ) -> RiskEvaluationState:
        with self._scope_locks(account_id, allocation_id):
            return self._evaluation_state(account_id, allocation_id)

    def reservation(self, reservation_id: ReservationId) -> CapitalReservation:
        existing = self._reservations.get(reservation_id)
        if existing is None:
            raise UnknownCapitalScopeError("reservation is not registered")
        with self._scope_locks(existing.account_id, existing.allocation_id):
            return self._reservation(reservation_id)

    def activate_lock(self, lock: SafetyLock) -> SafetyLock:
        if lock.scope is SafetyLockScope.PARENT_ACCOUNT:
            with self._parent_lock(lock.account_id):
                self._safety_locks.setdefault(lock.lock_id, lock)
                return self._safety_locks[lock.lock_id]
        if lock.allocation_id is None:
            raise ReservationTransitionError("scoped lock requires allocation identity")
        with self._scope_locks(lock.account_id, lock.allocation_id):
            allocation = self._allocation(lock.allocation_id)
            if allocation.account_id != lock.account_id:
                raise ReservationTransitionError("lock allocation belongs to another account")
            if lock.scope is SafetyLockScope.AGENT and allocation.agent_id != lock.agent_id:
                raise ReservationTransitionError("lock agent differs from allocation owner")
            self._safety_locks.setdefault(lock.lock_id, lock)
            return self._safety_locks[lock.lock_id]

    def reserve(
        self,
        proposal: TradeProposal,
        configuration: RiskConfiguration,
        preliminary_decision: RiskDecision,
        *,
        account_id: AccountId,
        allocation_id: AllocationId,
        evaluated_at: datetime,
        approval_binding: ApprovalBinding | None = None,
    ) -> ReservationAttempt:
        """Atomically revalidate and reserve both parent and allocation capacity."""
        with self._scope_locks(account_id, allocation_id):
            state = self._evaluation_state(account_id, allocation_id)
            mismatch = self._preliminary_mismatch_reasons(
                proposal,
                configuration,
                preliminary_decision,
                state,
            )
            if mismatch:
                rejected = self._risk_engine.rejection(
                    proposal,
                    configuration,
                    state,
                    evaluated_at=evaluated_at,
                    reasons=mismatch,
                )
                return ReservationAttempt(
                    status=ReservationAttemptStatus.REJECTED,
                    risk_decision=rejected,
                )

            key = (allocation_id, proposal.proposal_id)
            existing_id = self._proposal_reservations.get(key)
            if existing_id is not None:
                existing = self._reservation(existing_id)
                if existing.state is ReservationState.ACTIVE:
                    if existing.risk_decision_id != preliminary_decision.risk_decision_id:
                        rejected = self._risk_engine.rejection(
                            proposal,
                            configuration,
                            state,
                            evaluated_at=evaluated_at,
                            reasons={RiskRejectionCode.PRELIMINARY_DECISION_MISMATCH},
                        )
                        return ReservationAttempt(
                            status=ReservationAttemptStatus.REJECTED,
                            risk_decision=rejected,
                        )
                    return ReservationAttempt(
                        status=ReservationAttemptStatus.RESERVED,
                        risk_decision=preliminary_decision,
                        reservation=existing,
                        idempotent_replay=True,
                    )
                rejected = self._risk_engine.rejection(
                    proposal,
                    configuration,
                    state,
                    evaluated_at=evaluated_at,
                    reasons={RiskRejectionCode.DUPLICATE_TERMINAL_RESERVATION},
                )
                return ReservationAttempt(
                    status=ReservationAttemptStatus.REJECTED,
                    risk_decision=rejected,
                )

            final_decision = self._risk_engine.evaluate_for_reservation(
                proposal,
                configuration,
                state,
                evaluated_at=evaluated_at,
                approval_binding=approval_binding,
            )
            if final_decision.status is RiskDecisionStatus.REJECTED:
                return ReservationAttempt(
                    status=ReservationAttemptStatus.REJECTED,
                    risk_decision=final_decision,
                )
            sizing = final_decision.sizing_decision
            assert sizing is not None
            content: dict[str, object] = {
                "schema_version": "capital-reservation-v1",
                "proposal_id": proposal.proposal_id,
                "risk_decision_id": final_decision.risk_decision_id,
                "sizing_decision_id": sizing.sizing_decision_id,
                "risk_configuration_id": configuration.risk_configuration_id,
                "account_id": account_id,
                "allocation_id": allocation_id,
                "agent_id": proposal.agent_id,
                "instrument_id": proposal.instrument_id,
                "reserved_amount": sizing.reservation_amount,
                "approved_quantity": sizing.quantity,
                "currency": sizing.currency,
                "authority_context": proposal.authority_context.execution_dimensions,
                "approval_binding_id": (
                    approval_binding.approval_binding_id if approval_binding is not None else None
                ),
                "created_at": evaluated_at,
                "expires_at": proposal.valid_until,
                "state": ReservationState.ACTIVE,
                "transitioned_at": evaluated_at,
            }
            reservation = CapitalReservation(
                reservation_id=calculate_reservation_id(content),
                **content,  # type: ignore[arg-type]
            )

            parent = state.parent
            allocation = state.allocation
            amount = reservation.reserved_amount
            new_parent = ParentCapitalSnapshot.model_validate(
                {
                    **parent.model_dump(mode="python"),
                    "available_capital": parent.available_capital - amount,
                    "active_reserved_capital": parent.active_reserved_capital + amount,
                    "revision": parent.revision + 1,
                }
            )
            new_allocation = AllocationSnapshot.model_validate(
                {
                    **allocation.model_dump(mode="python"),
                    "available_capital": allocation.available_capital - amount,
                    "active_reserved_capital": allocation.active_reserved_capital + amount,
                    "active_reservation_count": allocation.active_reservation_count + 1,
                    "revision": allocation.revision + 1,
                }
            )

            self._parents[account_id] = new_parent
            self._allocations[allocation_id] = new_allocation
            self._reservations[reservation.reservation_id] = reservation
            self._proposal_reservations[key] = reservation.reservation_id
            return ReservationAttempt(
                status=ReservationAttemptStatus.RESERVED,
                risk_decision=final_decision,
                reservation=reservation,
            )

    def release(
        self,
        reservation_id: ReservationId,
        *,
        account_id: AccountId,
        allocation_id: AllocationId,
        agent_id: AgentId,
        transitioned_at: datetime,
    ) -> CapitalReservation:
        return self._transition(
            reservation_id,
            target=ReservationState.RELEASED,
            account_id=account_id,
            allocation_id=allocation_id,
            agent_id=agent_id,
            transitioned_at=transitioned_at,
        )

    def consume(
        self,
        reservation_id: ReservationId,
        *,
        account_id: AccountId,
        allocation_id: AllocationId,
        agent_id: AgentId,
        transitioned_at: datetime,
    ) -> CapitalReservation:
        return self._transition(
            reservation_id,
            target=ReservationState.CONSUMED,
            account_id=account_id,
            allocation_id=allocation_id,
            agent_id=agent_id,
            transitioned_at=transitioned_at,
        )

    def expire(
        self,
        reservation_id: ReservationId,
        *,
        account_id: AccountId,
        allocation_id: AllocationId,
        agent_id: AgentId,
        transitioned_at: datetime,
    ) -> CapitalReservation:
        return self._transition(
            reservation_id,
            target=ReservationState.EXPIRED,
            account_id=account_id,
            allocation_id=allocation_id,
            agent_id=agent_id,
            transitioned_at=transitioned_at,
        )

    def _transition(
        self,
        reservation_id: ReservationId,
        *,
        target: ReservationState,
        account_id: AccountId,
        allocation_id: AllocationId,
        agent_id: AgentId,
        transitioned_at: datetime,
    ) -> CapitalReservation:
        existing = self._reservation(reservation_id)
        with self._scope_locks(existing.account_id, existing.allocation_id):
            current = self._reservation(reservation_id)
            if (
                current.account_id != account_id
                or current.allocation_id != allocation_id
                or current.agent_id != agent_id
            ):
                raise ReservationTransitionError("reservation ownership mismatch")
            if current.state is target:
                return current
            if current.state is not ReservationState.ACTIVE:
                raise ReservationTransitionError(
                    f"cannot transition {current.state.value} reservation to {target.value}"
                )
            if target is ReservationState.EXPIRED and transitioned_at < current.expires_at:
                raise ReservationTransitionError("active reservation has not expired")

            parent = self._parent(account_id)
            allocation = self._allocation(allocation_id)
            amount = current.reserved_amount
            parent_update: dict[str, object] = {
                "active_reserved_capital": parent.active_reserved_capital - amount,
                "revision": parent.revision + 1,
            }
            allocation_update: dict[str, object] = {
                "active_reserved_capital": allocation.active_reserved_capital - amount,
                "active_reservation_count": allocation.active_reservation_count - 1,
                "revision": allocation.revision + 1,
            }
            if target is ReservationState.CONSUMED:
                parent_update["committed_capital"] = parent.committed_capital + amount
                allocation_update["committed_capital"] = allocation.committed_capital + amount
                allocation_update["instrument_committed_capital"] = (
                    allocation.instrument_committed_capital + amount
                )
            else:
                parent_update["available_capital"] = parent.available_capital + amount
                allocation_update["available_capital"] = allocation.available_capital + amount

            transitioned = CapitalReservation.model_validate(
                {
                    **current.model_dump(mode="python"),
                    "state": target,
                    "transitioned_at": transitioned_at,
                }
            )
            new_parent = ParentCapitalSnapshot.model_validate(
                {**parent.model_dump(mode="python"), **parent_update}
            )
            new_allocation = AllocationSnapshot.model_validate(
                {**allocation.model_dump(mode="python"), **allocation_update}
            )

            self._parents[account_id] = new_parent
            self._allocations[allocation_id] = new_allocation
            self._reservations[reservation_id] = transitioned
            return transitioned

    def _preliminary_mismatch_reasons(
        self,
        proposal: TradeProposal,
        configuration: RiskConfiguration,
        decision: RiskDecision,
        state: RiskEvaluationState,
    ) -> set[RiskRejectionCode]:
        if (
            decision.status is not RiskDecisionStatus.APPROVED_FOR_RESERVATION
            or decision.proposal_id != proposal.proposal_id
            or decision.agent_id != proposal.agent_id
            or decision.account_id != state.parent.account_id
            or decision.allocation_id != state.allocation.allocation_id
            or decision.risk_configuration_id != configuration.risk_configuration_id
        ):
            return {RiskRejectionCode.PRELIMINARY_DECISION_MISMATCH}
        return set()

    def _evaluation_state(
        self, account_id: AccountId, allocation_id: AllocationId
    ) -> RiskEvaluationState:
        return RiskEvaluationState(
            parent=self._parent(account_id),
            allocation=self._allocation(allocation_id),
            safety=self._safety_snapshot(account_id, allocation_id),
        )

    def _safety_snapshot(
        self, account_id: AccountId, allocation_id: AllocationId
    ) -> SafetyStateSnapshot:
        allocation = self._allocation(allocation_id)
        applicable = tuple(
            sorted(
                (
                    lock
                    for lock in self._safety_locks.values()
                    if lock.account_id == account_id
                    and (
                        lock.scope is SafetyLockScope.PARENT_ACCOUNT
                        or lock.allocation_id == allocation_id
                        or (
                            lock.scope is SafetyLockScope.AGENT
                            and lock.agent_id == allocation.agent_id
                        )
                    )
                ),
                key=lambda item: str(item.lock_id),
            )
        )
        return SafetyStateSnapshot(active_locks=applicable)

    def _parent(self, account_id: AccountId) -> ParentCapitalSnapshot:
        try:
            return self._parents[account_id]
        except KeyError as error:
            raise UnknownCapitalScopeError("parent account is not registered") from error

    def _allocation(self, allocation_id: AllocationId) -> AllocationSnapshot:
        try:
            return self._allocations[allocation_id]
        except KeyError as error:
            raise UnknownCapitalScopeError("allocation is not registered") from error

    def _reservation(self, reservation_id: ReservationId) -> CapitalReservation:
        try:
            return self._reservations[reservation_id]
        except KeyError as error:
            raise UnknownCapitalScopeError("reservation is not registered") from error

    @contextmanager
    def _parent_lock(self, account_id: AccountId) -> Iterator[None]:
        try:
            lock = self._parent_locks[account_id]
        except KeyError as error:
            raise UnknownCapitalScopeError("parent account is not registered") from error
        with lock:
            yield

    @contextmanager
    def _scope_locks(self, account_id: AccountId, allocation_id: AllocationId) -> Iterator[None]:
        try:
            parent_lock = self._parent_locks[account_id]
            allocation_lock = self._allocation_locks[allocation_id]
        except KeyError as error:
            raise UnknownCapitalScopeError("capital scope is not registered") from error
        with parent_lock, allocation_lock:
            yield
