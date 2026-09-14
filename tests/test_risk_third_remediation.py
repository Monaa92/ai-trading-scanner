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
    parent_loss_state,
    parent_snapshot,
    risk_policy,
    safety_state,
    state,
    trade_proposal,
)

from ai_trading_scanner.domain import (
    AgentId,
    AllocationId,
    RiskConfigurationId,
    TradeProposalId,
)
from ai_trading_scanner.risk import (
    AllocationSnapshot,
    InMemoryCapitalCoordinator,
    ReservationAttemptStatus,
    ReservationState,
    ReservationTransitionError,
    RiskDecision,
    RiskEngine,
    RiskEvaluationState,
    RiskRejectionCode,
    SizingDecision,
    UnknownCapitalScopeError,
    calculate_risk_decision_id,
    calculate_sizing_decision_id,
    create_safety_state,
)


def _register(store: InMemoryCapitalCoordinator, allocation: AllocationSnapshot) -> None:
    store.register_allocation(
        allocation,
        allocation_loss_state(
            str(allocation.allocated_capital),
            allocation_id=allocation.allocation_id,
            agent_id=allocation.agent_id,
        ),
    )


def test_parent_allocation_ownership_accepts_exact_boundary() -> None:
    store = InMemoryCapitalCoordinator()
    store.register_parent(parent_snapshot("100"), parent_loss_state("100"))

    _register(store, allocation_snapshot(agent="agent:A", allocation="allocation:A", capital="60"))
    _register(store, allocation_snapshot(agent="agent:B", allocation="allocation:B", capital="40"))

    assert store.allocation_snapshot(AllocationId.parse("allocation:A")).allocated_capital == 60
    assert store.allocation_snapshot(AllocationId.parse("allocation:B")).allocated_capital == 40


def test_parent_allocation_overflow_is_atomic_and_publishes_no_indexes() -> None:
    store = InMemoryCapitalCoordinator()
    store.register_parent(parent_snapshot("100"), parent_loss_state("100"))
    first = allocation_snapshot(agent="agent:A", allocation="allocation:A", capital="60")
    rejected = allocation_snapshot(agent="agent:B", allocation="allocation:B", capital="40.0001")
    accepted = allocation_snapshot(agent="agent:B", allocation="allocation:B", capital="40")
    _register(store, first)

    with pytest.raises(ReservationTransitionError, match="unassigned parent capital"):
        _register(store, rejected)
    with pytest.raises(UnknownCapitalScopeError):
        store.allocation_snapshot(rejected.allocation_id)

    _register(store, accepted)
    assert store.allocation_snapshot(accepted.allocation_id) == accepted


def test_concurrent_allocations_that_jointly_overflow_publish_exactly_one() -> None:
    store = InMemoryCapitalCoordinator()
    store.register_parent(parent_snapshot("100"), parent_loss_state("100"))
    allocations = (
        allocation_snapshot(agent="agent:A", allocation="allocation:A", capital="60"),
        allocation_snapshot(agent="agent:B", allocation="allocation:B", capital="60"),
    )
    barrier = Barrier(2)

    def register(index: int) -> str:
        barrier.wait()
        try:
            _register(store, allocations[index])
        except ReservationTransitionError:
            return "REJECTED"
        return "REGISTERED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(register, range(2), timeout=5))

    assert sorted(results) == ["REGISTERED", "REJECTED"]
    registered = 0
    for allocation in allocations:
        try:
            store.allocation_snapshot(allocation.allocation_id)
        except UnknownCapitalScopeError:
            continue
        registered += 1
    assert registered == 1


@pytest.mark.parametrize("terminal", ["release", "expire", "consume"])
def test_reservation_lifecycle_never_reclaims_parent_allocation_ownership(
    terminal: str,
) -> None:
    allocation = allocation_snapshot(capital="60")
    store = coordinator(parent=parent_snapshot("100"), allocations=(allocation,))
    proposal = trade_proposal(final_quantity=Decimal("0.1"))
    configured = risk_policy()
    preliminary = RiskEngine().evaluate(
        proposal,
        configured,
        store.evaluation_state(ACCOUNT_ID, allocation.allocation_id),
        evaluated_at=proposal.as_of,
    )
    attempt = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=allocation.allocation_id,
        evaluated_at=proposal.as_of,
    )
    reservation = attempt.reservation
    assert reservation is not None
    transitioned_at = (
        proposal.valid_until if terminal == "expire" else proposal.as_of + timedelta(seconds=1)
    )
    getattr(store, terminal)(
        reservation.reservation_id,
        account_id=reservation.account_id,
        allocation_id=reservation.allocation_id,
        agent_id=reservation.agent_id,
        transitioned_at=transitioned_at,
    )

    overflow = allocation_snapshot(agent="agent:B", allocation="allocation:B", capital="40.0001")
    with pytest.raises(ReservationTransitionError, match="unassigned parent capital"):
        _register(store, overflow)
    exact = allocation_snapshot(agent="agent:B", allocation="allocation:B", capital="40")
    _register(store, exact)

    parent = store.parent_snapshot(ACCOUNT_ID)
    first = store.allocation_snapshot(allocation.allocation_id)
    assert parent.total_capital == (
        parent.available_capital + parent.active_reserved_capital + parent.committed_capital
    )
    assert first.allocated_capital == (
        first.available_capital + first.active_reserved_capital + first.committed_capital
    )
    expected_state = {
        "release": ReservationState.RELEASED,
        "expire": ReservationState.EXPIRED,
        "consume": ReservationState.CONSUMED,
    }[terminal]
    assert store.reservation(reservation.reservation_id).state is expected_state


def test_allocation_registration_and_reservation_share_parent_lock_order_without_deadlock() -> None:
    first = allocation_snapshot(capital="60")
    second = allocation_snapshot(agent="agent:B", allocation="allocation:B", capital="40")
    store = coordinator(parent=parent_snapshot("100"), allocations=(first,))
    proposal = trade_proposal(final_quantity=Decimal("0.1"))
    configured = risk_policy()
    preliminary = RiskEngine().evaluate(
        proposal,
        configured,
        store.evaluation_state(ACCOUNT_ID, first.allocation_id),
        evaluated_at=proposal.as_of,
    )
    barrier = Barrier(2)

    def reserve() -> ReservationAttemptStatus:
        barrier.wait()
        return store.reserve(
            proposal,
            configured,
            preliminary,
            account_id=ACCOUNT_ID,
            allocation_id=first.allocation_id,
            evaluated_at=proposal.as_of,
        ).status

    def register() -> str:
        barrier.wait()
        _register(store, second)
        return "REGISTERED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        reserve_future = pool.submit(reserve)
        register_future = pool.submit(register)
        assert reserve_future.result(timeout=5) is ReservationAttemptStatus.RESERVED
        assert register_future.result(timeout=5) == "REGISTERED"


def test_allocation_currency_mismatch_is_atomic() -> None:
    store = InMemoryCapitalCoordinator()
    store.register_parent(parent_snapshot("100"), parent_loss_state("100"))
    wrong = allocation_snapshot(capital="50").model_copy(update={"currency": "EUR"})
    with pytest.raises(ReservationTransitionError, match="currency differs"):
        _register(store, wrong)

    valid = allocation_snapshot(capital="50")
    _register(store, valid)
    assert store.allocation_snapshot(valid.allocation_id) == valid


@pytest.mark.parametrize("quantity", [Decimal("0.8"), Decimal("1.0")])
def test_recomputed_future_risk_quantity_cannot_claim_original_provenance(
    quantity: Decimal,
) -> None:
    proposal = trade_proposal()
    configured = risk_policy()
    original = RiskEngine().evaluate(proposal, configured, state(), evaluated_at=proposal.as_of)
    sizing = original.sizing_decision
    assert sizing is not None
    content = sizing.model_dump(mode="python", exclude={"sizing_decision_id"})
    content["quantity"] = quantity
    content["modeled_risk_amount"] = quantity * sizing.unit_modeled_loss
    content["reservation_amount"] = quantity * sizing.cash_per_unit
    content["sizing_decision_id"] = calculate_sizing_decision_id(content)

    with pytest.raises(ValidationError, match="deterministic result of bound inputs"):
        SizingDecision.model_validate(content)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("proposal_id", TradeProposalId.parse(f"sha256:{'b' * 64}")),
        ("risk_configuration_id", RiskConfigurationId.parse(f"sha256:{'c' * 64}")),
    ],
)
def test_rejected_risk_decision_cannot_claim_arbitrary_source_identity(
    field: str,
    replacement: object,
) -> None:
    proposal = trade_proposal()
    original = RiskEngine().evaluate(
        proposal,
        risk_policy(),
        state(),
        evaluated_at=proposal.valid_until,
    )
    content = original.model_dump(mode="python", exclude={"risk_decision_id"})
    content[field] = replacement
    content["risk_decision_id"] = calculate_risk_decision_id(content)

    with pytest.raises(ValidationError, match="source attribution is inconsistent"):
        RiskDecision.model_validate(content)


def test_rejected_risk_decision_cannot_substitute_foreign_safety_evidence() -> None:
    proposal = trade_proposal()
    original = RiskEngine().evaluate(
        proposal,
        risk_policy(),
        state(),
        evaluated_at=proposal.valid_until,
    )
    foreign = safety_state(
        allocation_id=AllocationId.parse("allocation:foreign"),
        agent_id=AgentId.parse("agent:foreign"),
    )
    content = original.model_dump(mode="python", exclude={"risk_decision_id"})
    content["evaluated_safety_state"] = foreign
    content["risk_decision_id"] = calculate_risk_decision_id(content)

    with pytest.raises(ValidationError, match="differs from bound source state"):
        RiskDecision.model_validate(content)


def test_rejected_risk_decision_requires_causal_stale_safety_reason() -> None:
    proposal = trade_proposal()
    stale_at = proposal.as_of + timedelta(seconds=1)
    stale_safety = create_safety_state(
        agent_loss_state=allocation_loss_state(valid_until=stale_at),
        parent_loss_state=parent_loss_state(valid_until=stale_at),
    )
    snapshot = state(safety=stale_safety)
    original = RiskEngine().evaluate(
        proposal,
        risk_policy(),
        snapshot,
        evaluated_at=stale_at,
    )
    assert RiskRejectionCode.STALE_SAFETY_STATE in original.reason_codes
    content = original.model_dump(mode="python", exclude={"risk_decision_id"})
    content["reason_codes"] = (RiskRejectionCode.TRADING_LOCK,)
    content["risk_decision_id"] = calculate_risk_decision_id(content)

    with pytest.raises(ValidationError, match="causal evidence"):
        RiskDecision.model_validate(content)


def test_risk_evaluation_state_rejects_cross_session_safety_evidence() -> None:
    mismatched = create_safety_state(
        agent_loss_state=allocation_loss_state(),
        parent_loss_state=parent_loss_state(
            session_id="XNYS:2024-07-03:exchange-calendars-4.13.2",
            session_start_at=trade_proposal().as_of + timedelta(days=1),
            session_end_at=trade_proposal().valid_until + timedelta(days=1),
            valid_until=trade_proposal().valid_until + timedelta(days=1),
            observed_at=trade_proposal().as_of + timedelta(days=1),
            effective_at=trade_proposal().as_of + timedelta(days=1),
        ),
    )

    with pytest.raises(ValidationError, match="share one session boundary"):
        RiskEvaluationState(
            parent=parent_snapshot(),
            allocation=allocation_snapshot(),
            safety=mismatched,
        )
