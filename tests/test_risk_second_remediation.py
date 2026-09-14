from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from pydantic import ValidationError
from risk_helpers import (
    ACCOUNT_ID,
    AGENT_ID,
    ALLOCATION_ID,
    LOSS_OBSERVED_AT,
    SESSION_END_AT,
    SESSION_ID,
    SESSION_START_AT,
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

from ai_trading_scanner.domain import AccountId, AgentId, AllocationId
from ai_trading_scanner.risk import (
    DuplicateCapitalScopeError,
    InMemoryCapitalCoordinator,
    ReservationAttemptStatus,
    ReservationTransitionError,
    RiskDecision,
    RiskDecisionStatus,
    RiskEngine,
    RiskRejectionCode,
    calculate_risk_decision_id,
    calculate_sizing_decision_id,
    create_loss_state,
    create_safety_state,
)


def test_second_allocation_for_same_agent_is_rejected_before_risk_accounting() -> None:
    store = coordinator()
    second = allocation_snapshot(allocation="allocation:A2")

    with pytest.raises(DuplicateCapitalScopeError, match="already has an active allocation"):
        store.register_allocation(
            second,
            allocation_loss_state(allocation_id=second.allocation_id),
        )


@pytest.mark.parametrize(
    "first",
    [
        allocation_snapshot(capital="100").model_copy(
            update={
                "available_capital": Decimal("70"),
                "active_reserved_capital": Decimal("30"),
                "active_reservation_count": 1,
            }
        ),
        allocation_snapshot(capital="100").model_copy(
            update={
                "available_capital": Decimal("40"),
                "committed_capital": Decimal("60"),
            }
        ),
    ],
    ids=["reserved-downside-and-count", "committed-exposure"],
)
def test_second_allocation_cannot_fragment_agent_limits(first) -> None:  # type: ignore[no-untyped-def]
    store = InMemoryCapitalCoordinator()
    store.register_parent(parent_snapshot("200"), parent_loss_state("200"))
    store.register_allocation(first, allocation_loss_state())
    second = allocation_snapshot(allocation="allocation:A2")

    with pytest.raises(DuplicateCapitalScopeError):
        store.register_allocation(
            second,
            allocation_loss_state(allocation_id=second.allocation_id),
        )


def test_concurrent_same_agent_registration_publishes_exactly_one_allocation() -> None:
    store = InMemoryCapitalCoordinator()
    store.register_parent(parent_snapshot("200"), parent_loss_state("200"))
    allocations = (
        allocation_snapshot(allocation="allocation:A1"),
        allocation_snapshot(allocation="allocation:A2"),
    )
    barrier = Barrier(2)

    def register(index: int) -> str:
        allocation = allocations[index]
        barrier.wait()
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


@pytest.mark.parametrize("terminal", ["release", "expire"])
def test_terminal_reservation_does_not_create_second_allocation_eligibility(terminal: str) -> None:
    proposal = trade_proposal()
    configured = risk_policy()
    store = coordinator()
    preliminary = RiskEngine().evaluate(
        proposal,
        configured,
        store.evaluation_state(ACCOUNT_ID, ALLOCATION_ID),
        evaluated_at=proposal.as_of,
    )
    attempt = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=ALLOCATION_ID,
        evaluated_at=proposal.as_of,
    )
    assert attempt.reservation is not None
    transition = getattr(store, terminal)
    transition(
        attempt.reservation.reservation_id,
        account_id=ACCOUNT_ID,
        allocation_id=ALLOCATION_ID,
        agent_id=AGENT_ID,
        transitioned_at=(
            proposal.valid_until if terminal == "expire" else proposal.as_of + timedelta(seconds=1)
        ),
    )
    second = allocation_snapshot(allocation="allocation:A2")

    with pytest.raises(DuplicateCapitalScopeError):
        store.register_allocation(
            second,
            allocation_loss_state(allocation_id=second.allocation_id),
        )


def test_legitimate_risk_evidence_round_trips_through_json_validation() -> None:
    proposal = trade_proposal()
    decision = RiskEngine().evaluate(proposal, risk_policy(), state(), evaluated_at=proposal.as_of)

    assert RiskDecision.model_validate_json(decision.model_dump_json()) == decision


def test_coherent_sizing_and_risk_forgery_cannot_retain_original_provenance() -> None:
    proposal = trade_proposal()
    configured = risk_policy()
    original = RiskEngine().evaluate(proposal, configured, state(), evaluated_at=proposal.as_of)
    assert original.sizing_decision is not None
    decision_content = original.model_dump(mode="python", exclude={"risk_decision_id"})
    sizing = decision_content["sizing_decision"]
    assert isinstance(sizing, dict)
    sizing.pop("sizing_decision_id")
    sizing["entry_price"] = original.sizing_decision.entry_price - Decimal("1")
    sizing["stop_price"] = original.sizing_decision.stop_price - Decimal("1")
    sizing["unit_risk"] = sizing["entry_price"] - sizing["stop_price"]
    sizing["unit_modeled_loss"] = (
        sizing["unit_risk"] + sizing["entry_price"] * sizing["round_trip_cost_return"]
    )
    sizing["cash_per_unit"] = sizing["entry_price"] * (
        Decimal(1) + sizing["round_trip_cost_return"]
    )
    sizing["modeled_risk_amount"] = sizing["quantity"] * sizing["unit_modeled_loss"]
    sizing["reservation_amount"] = sizing["quantity"] * sizing["cash_per_unit"]
    sizing["sizing_decision_id"] = calculate_sizing_decision_id(sizing)
    decision_content["risk_decision_id"] = calculate_risk_decision_id(decision_content)

    with pytest.raises(ValidationError, match="immutable proposal content"):
        RiskDecision.model_validate(decision_content)


def test_reidentified_configuration_forgery_cannot_retain_original_provenance() -> None:
    proposal = trade_proposal()
    original = RiskEngine().evaluate(proposal, risk_policy(), state(), evaluated_at=proposal.as_of)
    assert original.sizing_decision is not None
    content = original.model_dump(mode="python", exclude={"risk_decision_id"})
    sizing = content["sizing_decision"]
    assert isinstance(sizing, dict)
    sizing["quantity_increment"] = Decimal("0.01")
    sizing["sizing_decision_id"] = calculate_sizing_decision_id(
        {key: value for key, value in sizing.items() if key != "sizing_decision_id"}
    )
    content["risk_decision_id"] = calculate_risk_decision_id(content)

    with pytest.raises(ValidationError, match="immutable risk configuration"):
        RiskDecision.model_validate(content)


def test_reidentified_allowed_risk_cannot_disagree_with_bound_configuration() -> None:
    proposal = trade_proposal()
    original = RiskEngine().evaluate(proposal, risk_policy(), state(), evaluated_at=proposal.as_of)
    assert original.sizing_decision is not None
    content = original.model_dump(mode="python", exclude={"risk_decision_id"})
    sizing = content["sizing_decision"]
    assert isinstance(sizing, dict)
    sizing["allowed_risk_amount"] = original.sizing_decision.allowed_risk_amount - Decimal("1")
    sizing["sizing_decision_id"] = calculate_sizing_decision_id(
        {key: value for key, value in sizing.items() if key != "sizing_decision_id"}
    )
    content["risk_decision_id"] = calculate_risk_decision_id(content)

    with pytest.raises(ValidationError, match="allowed risk does not match immutable inputs"):
        RiskDecision.model_validate(content)


def test_parent_loss_state_from_another_account_is_rejected() -> None:
    store = InMemoryCapitalCoordinator()
    wrong = parent_loss_state(account_id=AccountId.parse("account:other"))

    with pytest.raises(ReservationTransitionError, match="attribution mismatch"):
        store.register_parent(parent_snapshot(), wrong)


@pytest.mark.parametrize(
    ("allocation_id", "agent_id"),
    [
        (AllocationId.parse("allocation:other"), AGENT_ID),
        (ALLOCATION_ID, AgentId.parse("agent:other")),
    ],
    ids=["cross-allocation", "cross-agent"],
)
def test_misattributed_allocation_loss_state_is_rejected(
    allocation_id: AllocationId, agent_id: AgentId
) -> None:
    store = InMemoryCapitalCoordinator()
    store.register_parent(parent_snapshot(), parent_loss_state())
    allocation = allocation_snapshot()

    with pytest.raises(ReservationTransitionError, match="attribution mismatch"):
        store.register_allocation(
            allocation,
            allocation_loss_state(allocation_id=allocation_id, agent_id=agent_id),
        )


def test_previous_session_loss_evidence_fails_closed() -> None:
    proposal = trade_proposal()
    previous_start = SESSION_START_AT - timedelta(days=1)
    previous_end = SESSION_END_AT - timedelta(days=1)
    previous_observed = LOSS_OBSERVED_AT - timedelta(days=1)
    previous_agent = allocation_loss_state(
        session_id="XNYS:2024-07-01:exchange-calendars-4.13.2",
        session_start_at=previous_start,
        session_end_at=previous_end,
        observed_at=previous_observed,
        effective_at=previous_observed,
        valid_until=previous_end,
    )
    previous_parent = parent_loss_state(
        session_id="XNYS:2024-07-01:exchange-calendars-4.13.2",
        session_start_at=previous_start,
        session_end_at=previous_end,
        observed_at=previous_observed,
        effective_at=previous_observed,
        valid_until=previous_end,
    )
    decision = RiskEngine().evaluate(
        proposal,
        risk_policy(),
        state(
            safety=create_safety_state(
                agent_loss_state=previous_agent,
                parent_loss_state=previous_parent,
            )
        ),
        evaluated_at=proposal.as_of,
    )

    assert RiskRejectionCode.SAFETY_STATE_MISMATCH in decision.reason_codes
    assert RiskRejectionCode.STALE_SAFETY_STATE in decision.reason_codes


def test_stale_loss_observation_fails_at_exact_validity_boundary() -> None:
    proposal = trade_proposal()
    observed = proposal.as_of - timedelta(seconds=2)
    safety = create_safety_state(
        agent_loss_state=allocation_loss_state(
            observed_at=observed,
            effective_at=observed,
            valid_until=proposal.as_of,
        ),
        parent_loss_state=parent_loss_state(
            observed_at=observed,
            effective_at=observed,
            valid_until=proposal.as_of,
        ),
    )

    decision = RiskEngine().evaluate(
        proposal, risk_policy(), state(safety=safety), evaluated_at=proposal.as_of
    )

    assert RiskRejectionCode.STALE_SAFETY_STATE in decision.reason_codes


def test_future_loss_observation_fails_closed() -> None:
    proposal = trade_proposal()
    future = proposal.as_of + timedelta(seconds=1)
    safety = create_safety_state(
        agent_loss_state=allocation_loss_state(
            observed_at=future,
            effective_at=future,
            valid_until=future + timedelta(minutes=1),
        ),
        parent_loss_state=parent_loss_state(
            observed_at=future,
            effective_at=future,
            valid_until=future + timedelta(minutes=1),
        ),
    )

    decision = RiskEngine().evaluate(
        proposal, risk_policy(), state(safety=safety), evaluated_at=proposal.as_of
    )

    assert RiskRejectionCode.FUTURE_SAFETY_STATE in decision.reason_codes


def test_loss_state_rejects_causally_invalid_timestamps() -> None:
    with pytest.raises(ValidationError, match="causal or freshness ordering"):
        create_loss_state(
            **allocation_loss_state().model_dump(
                mode="python", exclude={"loss_state_id", "schema_version"}
            )
            | {"effective_at": LOSS_OBSERVED_AT + timedelta(seconds=1)}
        )


def test_loss_state_revision_and_time_cannot_regress() -> None:
    store = coordinator()
    store.update_allocation_loss_state(
        ALLOCATION_ID,
        allocation_loss_state(
            revision=2,
            observed_at=LOSS_OBSERVED_AT + timedelta(seconds=2),
            effective_at=LOSS_OBSERVED_AT + timedelta(seconds=2),
        ),
    )

    with pytest.raises(ReservationTransitionError, match="revision must increase"):
        store.update_allocation_loss_state(
            ALLOCATION_ID,
            allocation_loss_state(
                revision=1,
                observed_at=LOSS_OBSERVED_AT + timedelta(seconds=3),
                effective_at=LOSS_OBSERVED_AT + timedelta(seconds=3),
            ),
        )
    with pytest.raises(ReservationTransitionError, match="observation time cannot regress"):
        store.update_allocation_loss_state(
            ALLOCATION_ID,
            allocation_loss_state(revision=3),
        )


def test_current_attributed_loss_state_allows_normal_evaluation() -> None:
    proposal = trade_proposal()
    decision = RiskEngine().evaluate(
        proposal,
        risk_policy(),
        state(safety=safety_state()),
        evaluated_at=proposal.as_of,
    )

    assert decision.status is RiskDecisionStatus.APPROVED_FOR_RESERVATION


def test_freshness_change_between_preflight_and_reservation_is_revalidated() -> None:
    proposal = trade_proposal()
    configured = risk_policy()
    store = coordinator()
    preliminary = RiskEngine().evaluate(
        proposal,
        configured,
        store.evaluation_state(ACCOUNT_ID, ALLOCATION_ID),
        evaluated_at=proposal.as_of,
    )
    stale_observed = proposal.as_of + timedelta(microseconds=1)
    store.update_allocation_loss_state(
        ALLOCATION_ID,
        allocation_loss_state(
            revision=1,
            observed_at=stale_observed,
            effective_at=stale_observed,
            valid_until=proposal.as_of + timedelta(microseconds=2),
        ),
    )
    store.update_parent_loss_state(
        ACCOUNT_ID,
        parent_loss_state(
            revision=1,
            observed_at=stale_observed,
            effective_at=stale_observed,
            valid_until=proposal.as_of + timedelta(microseconds=2),
        ),
    )

    attempt = store.reserve(
        proposal,
        configured,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=ALLOCATION_ID,
        evaluated_at=proposal.as_of + timedelta(microseconds=2),
    )

    assert attempt.status is ReservationAttemptStatus.REJECTED
    assert RiskRejectionCode.STALE_SAFETY_STATE in attempt.risk_decision.reason_codes


def test_loss_state_session_identity_is_bound_into_decision_identity() -> None:
    proposal = trade_proposal()
    configured = risk_policy()
    first = RiskEngine().evaluate(proposal, configured, state(), evaluated_at=proposal.as_of)
    renamed_safety = create_safety_state(
        agent_loss_state=allocation_loss_state(session_id=SESSION_ID + ":reconciled"),
        parent_loss_state=parent_loss_state(session_id=SESSION_ID + ":reconciled"),
    )
    second = RiskEngine().evaluate(
        proposal,
        configured,
        state(safety=renamed_safety),
        evaluated_at=proposal.as_of,
    )

    assert first.evaluated_safety_state.safety_state_id != (
        second.evaluated_safety_state.safety_state_id
    )
    assert first.risk_decision_id != second.risk_decision_id
