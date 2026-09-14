from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from risk_helpers import ACCOUNT_ID, ALLOCATION_ID, coordinator, risk_policy, state, trade_proposal
from simulation_helpers import (
    cost_configuration,
    execution_configuration,
    run_manifest,
    simulated_fill,
    simulated_order,
)
from strategy_helpers import strategy_bars

from ai_trading_scanner.domain.content_identity import canonical_json_bytes
from ai_trading_scanner.market_data import (
    AdjustmentMethod,
    AvailabilityMode,
    CanonicalDataset,
    DataProvenance,
    HistoricalBar,
    QualityStatus,
    Timeframe,
    UsEquitiesCalendar,
)
from ai_trading_scanner.risk import CapitalReservation, RiskEngine, calculate_reservation_id
from ai_trading_scanner.simulation import (
    MarketEventReference,
    PositionChange,
    PositionChangeKind,
    SimulatedFill,
    SimulatedOrder,
    ValidatedExecutionChain,
    calculate_fill_costs,
    calculate_market_event_id,
    calculate_position_change_id,
    calculate_position_id,
    calculate_simulated_fill_id,
    calculate_simulated_order_id,
    select_session_bounded_next_bar,
)
from ai_trading_scanner.strategies import (
    StrategyOutcome,
    TradeProposal,
    TradeProposalDecision,
    calculate_strategy_decision_id,
    calculate_trade_proposal_id,
)


def _dataset_and_proposal() -> tuple[CanonicalDataset, TradeProposal]:
    closes = ["100"] * 54 + ["101", "102", "101", "102", "103", "105", "106", "107", "108"]
    highs = [str(Decimal(close) + Decimal("0.5")) for close in closes]
    highs[50] = "110"
    highs[58] = "104"
    highs[59] = "105.5"
    lows = ["99.5"] * len(closes)
    lows[56] = "100.5"
    bars = strategy_bars(closes, highs=highs, lows=lows)
    provenance = DataProvenance(
        provider="synthetic-execution-chain",
        timeframe=Timeframe.MINUTE_5,
        source_timezone="America/New_York",
        ingested_at=datetime(2024, 12, 31, tzinfo=UTC),
        adjustment_method=AdjustmentMethod.RAW,
        availability_mode=AvailabilityMode.MODELED,
        modeled_publication_delay_seconds=5,
        calendar_version="exchange-calendars-4.13.2",
        normalization_version="normalizer-v1",
        quality_status=QualityStatus.PASS,
    )
    dataset = CanonicalDataset.create(provenance, bars)
    original = trade_proposal(final_quantity=Decimal("0.1"), validity_extension_minutes=10)
    content = original.model_dump(mode="python", exclude={"proposal_id"})
    content.update(
        {
            "dataset_id": dataset.dataset_id,
            "market_data_slice_hash_sha256": hashlib.sha256(
                canonical_json_bytes(bars[:60])
            ).hexdigest(),
        }
    )
    proposal = TradeProposal(
        proposal_id=calculate_trade_proposal_id(content),
        **content,
    )
    return dataset, proposal


def _valid_chain() -> ValidatedExecutionChain:
    dataset, proposal = _dataset_and_proposal()
    decision_content: dict[str, object] = {
        "schema_version": "strategy-decision-v1",
        "agent_id": proposal.agent_id,
        "strategy_id": proposal.strategy_id,
        "strategy_version": proposal.strategy_version,
        "strategy_configuration_id": proposal.strategy_configuration_id,
        "instrument_id": proposal.instrument_id,
        "as_of": proposal.as_of,
        "dataset_id": proposal.dataset_id,
        "market_data_slice_hash_sha256": proposal.market_data_slice_hash_sha256,
        "indicator_configuration_ids": proposal.indicator_configuration_ids,
        "evidence": proposal.evidence,
        "quality_findings": proposal.quality_findings,
        "outcome": StrategyOutcome.TRADE_PROPOSAL,
        "reasons": (),
        "detail": None,
        "proposal": proposal,
    }
    strategy_decision = TradeProposalDecision.model_validate(
        {
            "decision_id": calculate_strategy_decision_id(decision_content),
            **decision_content,
        }
    )
    policy = risk_policy(quantity_increment=Decimal("0.1"))
    evaluation_state = state()
    preliminary = RiskEngine().evaluate(
        proposal, policy, evaluation_state, evaluated_at=proposal.as_of
    )
    attempt = coordinator().reserve(
        proposal,
        policy,
        preliminary,
        account_id=ACCOUNT_ID,
        allocation_id=ALLOCATION_ID,
        evaluated_at=proposal.as_of,
    )
    reservation = attempt.reservation
    assert reservation is not None
    risk_decision = attempt.risk_decision
    sizing = risk_decision.sizing_decision
    assert sizing is not None
    execution = execution_configuration(
        routing_latency_seconds=0, quantity_increment=Decimal("0.1")
    )
    costs = cost_configuration()
    manifest = run_manifest(
        dataset_id=dataset.dataset_id,
        account_id=ACCOUNT_ID,
        allocation_id=ALLOCATION_ID,
        agent_id=proposal.agent_id,
        strategy_id=proposal.strategy_id,
        strategy_configuration_id=proposal.strategy_configuration_id,
        strategy_version=proposal.strategy_version,
        indicator_configuration_ids=proposal.indicator_configuration_ids,
        risk_configuration_id=policy.risk_configuration_id,
        management_mandate_id=proposal.management_mandate.mandate_id,
        configuration_version_id=proposal.authority_context.configuration_version_id,
        execution_model_id=execution.execution_model_id,
        cost_model_id=costs.cost_model_id,
        starting_capital="100",
        execution_dimensions=proposal.authority_context.execution_dimensions,
    )
    order = simulated_order(
        run_id=manifest.run_id,
        account_id=manifest.account_id,
        allocation_id=manifest.allocation_id,
        agent_id=manifest.agent_id,
        strategy_id=manifest.strategy_id,
        management_mandate_id=manifest.management_mandate_id,
        proposal_id=proposal.proposal_id,
        strategy_decision_id=strategy_decision.decision_id,
        risk_decision_id=risk_decision.risk_decision_id,
        reservation_id=reservation.reservation_id,
        instrument_id=proposal.instrument_id,
        quantity=sizing.quantity,
        currency=proposal.entry.currency,
        execution_model_id=execution.execution_model_id,
        decision_at=proposal.as_of,
        submitted_at=proposal.as_of,
        eligible_at=proposal.as_of,
        valid_until=proposal.valid_until,
    )
    source_bar = next(bar for bar in dataset.bars if bar.start_at > order.eligible_at)
    market_content: dict[str, object] = {
        "schema_version": "market-event-reference-v1",
        "dataset_id": dataset.dataset_id,
        "instrument_id": source_bar.instrument_id,
        "interval_start_at": source_bar.start_at,
        "event_at": source_bar.end_at,
        "available_at": source_bar.available_at,
        "source_record_id": source_bar.source_record_id,
    }
    market = MarketEventReference.model_validate(
        {"market_event_id": calculate_market_event_id(market_content), **market_content}
    )
    fill_costs = calculate_fill_costs(costs, order.quantity, source_bar.open)
    fill = simulated_fill(
        run_id=manifest.run_id,
        order_id=order.order_id,
        account_id=manifest.account_id,
        allocation_id=manifest.allocation_id,
        agent_id=manifest.agent_id,
        proposal_id=proposal.proposal_id,
        risk_decision_id=risk_decision.risk_decision_id,
        reservation_id=reservation.reservation_id,
        instrument_id=proposal.instrument_id,
        quantity=order.quantity,
        fill_price=source_bar.open,
        currency=source_bar.currency,
        execution_model_id=execution.execution_model_id,
        market_event=market,
        submitted_at=order.submitted_at,
        eligible_at=order.eligible_at,
        execution_interval_start_at=source_bar.start_at,
        execution_interval_end_at=source_bar.end_at,
        simulated_execution_at=source_bar.start_at,
        fill_at=source_bar.available_at,
        costs=fill_costs,
    )
    position_id = calculate_position_id(
        manifest.run_id,
        manifest.account_id,
        manifest.allocation_id,
        manifest.agent_id,
        proposal.instrument_id,
        proposal.proposal_id,
    )
    change_content: dict[str, object] = {
        "schema_version": "position-change-v1",
        "run_id": manifest.run_id,
        "account_id": manifest.account_id,
        "allocation_id": manifest.allocation_id,
        "agent_id": manifest.agent_id,
        "position_id": position_id,
        "proposal_id": proposal.proposal_id,
        "order_id": order.order_id,
        "fill_id": fill.fill_id,
        "management_mandate_id": proposal.management_mandate.mandate_id,
        "kind": PositionChangeKind.OPEN,
        "previous_quantity": Decimal("0"),
        "quantity_delta": fill.quantity,
        "new_quantity": fill.quantity,
        "changed_at": fill.fill_at,
    }
    change = PositionChange.model_validate(
        {"position_change_id": calculate_position_change_id(change_content), **change_content}
    )
    return ValidatedExecutionChain(
        manifest=manifest,
        strategy_decision=strategy_decision,
        risk_decision=risk_decision,
        reservation=reservation,
        execution_configuration=execution,
        cost_configuration=costs,
        order=order,
        dataset=dataset,
        fill=fill,
        position_change=change,
    )


def _rebuild_order(order: SimulatedOrder, **changes: object) -> SimulatedOrder:
    content = order.model_dump(mode="python", exclude={"order_id"})
    content.update(changes)
    return SimulatedOrder.model_validate(
        {"order_id": calculate_simulated_order_id(content), **content}
    )


def _rebuild_fill(fill: SimulatedFill, **changes: object) -> SimulatedFill:
    content = fill.model_dump(mode="python", exclude={"fill_id"})
    content.update(changes)
    return SimulatedFill.model_validate(
        {"fill_id": calculate_simulated_fill_id(content), **content}
    )


def _session_selection_fixture(
    session_date: date,
    *,
    include_same_session_candidate: bool,
    include_next_session_candidate: bool = False,
    near_close: bool = False,
) -> tuple[CanonicalDataset, TradeProposal, SimulatedOrder]:
    chain = _valid_chain()
    template = chain.dataset.bars[0]
    calendar = UsEquitiesCalendar()
    session = calendar.session_for_date(session_date)
    assert session is not None
    base = session.close_at - timedelta(minutes=20) if near_close else session.open_at

    def bar(
        index: int, *, start: datetime | None = None, session_id: str | None = None
    ) -> HistoricalBar:
        start_at = start or base + timedelta(minutes=index * 5)
        content = template.model_dump(mode="python")
        content.update(
            {
                "session_id": session_id or session.session_id,
                "start_at": start_at,
                "end_at": start_at + timedelta(minutes=5),
                "available_at": start_at + timedelta(minutes=5, seconds=5),
                "source_record_id": f"session-boundary-{start_at.isoformat()}",
            }
        )
        return type(template).model_validate(content)

    causal = (bar(0), bar(1))
    bars = list(causal)
    if include_same_session_candidate:
        bars.append(bar(3))
    if include_next_session_candidate:
        next_date = session_date + timedelta(days=1)
        next_session = calendar.session_for_date(next_date)
        while next_session is None:
            next_date += timedelta(days=1)
            next_session = calendar.session_for_date(next_date)
        bars.append(
            bar(
                0,
                start=next_session.open_at,
                session_id=next_session.session_id,
            )
        )
    dataset = CanonicalDataset.create(chain.dataset.provenance, tuple(bars))
    proposal_content = chain.strategy_decision.proposal.model_dump(
        mode="python", exclude={"proposal_id"}
    )
    as_of = causal[-1].available_at
    proposal_content.update(
        {
            "generated_at": as_of,
            "as_of": as_of,
            "valid_until": session.close_at + timedelta(days=3),
            "dataset_id": dataset.dataset_id,
            "market_data_slice_hash_sha256": hashlib.sha256(
                canonical_json_bytes(causal)
            ).hexdigest(),
        }
    )
    proposal = TradeProposal.model_validate(
        {"proposal_id": calculate_trade_proposal_id(proposal_content), **proposal_content}
    )
    order = _rebuild_order(
        chain.order,
        proposal_id=proposal.proposal_id,
        instrument_id=proposal.instrument_id,
        decision_at=as_of,
        submitted_at=as_of,
        eligible_at=as_of,
        valid_until=proposal.valid_until,
    )
    return dataset, proposal, order


def _chain_with_reidentified_reservation(**changes: object) -> dict[str, object]:
    chain = _valid_chain()
    reservation_content = chain.reservation.model_dump(mode="python")
    reservation_content.update(changes)
    reservation_content["reservation_id"] = calculate_reservation_id(reservation_content)
    reservation = CapitalReservation.model_validate(reservation_content)
    order = _rebuild_order(chain.order, reservation_id=reservation.reservation_id)
    fill = _rebuild_fill(
        chain.fill,
        order_id=order.order_id,
        reservation_id=reservation.reservation_id,
    )
    change_content = chain.position_change.model_dump(mode="python", exclude={"position_change_id"})
    change_content.update({"order_id": order.order_id, "fill_id": fill.fill_id})
    change = PositionChange.model_validate(
        {
            "position_change_id": calculate_position_change_id(change_content),
            **change_content,
        }
    )
    content = chain.model_dump(mode="python")
    content.update(
        {
            "reservation": reservation,
            "order": order,
            "fill": fill,
            "position_change": change,
        }
    )
    return content


def test_valid_chain_enforces_zero_latency_and_canonical_next_open() -> None:
    chain = _valid_chain()
    assert chain.order.eligible_at == chain.order.submitted_at
    assert chain.fill.fill_price == next(
        bar.open
        for bar in chain.dataset.bars
        if bar.start_at == chain.fill.execution_interval_start_at
    )


def test_exact_authoritative_reservation_economics_are_accepted() -> None:
    chain = _valid_chain()
    sizing = chain.risk_decision.sizing_decision
    assert sizing is not None
    assert chain.reservation.reserved_amount == sizing.reservation_amount
    assert chain.reservation.reserved_downside == sizing.modeled_risk_amount


@pytest.mark.parametrize(
    "changes",
    [
        {"reserved_amount": Decimal("0.01")},
        {"reserved_downside": Decimal("0.01")},
        {"instrument_id": "XNYS:MSFT"},
        {"currency": "EUR"},
    ],
    ids=["reserved-amount", "reserved-downside", "instrument", "currency"],
)
def test_reidentified_reservation_economic_tampering_is_rejected(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="reservation does not match approved risk sizing"):
        ValidatedExecutionChain.model_validate(_chain_with_reidentified_reservation(**changes))


def test_reidentified_reservation_creation_time_tampering_is_rejected() -> None:
    chain = _valid_chain()
    changed_at = chain.reservation.created_at + timedelta(seconds=1)
    content = _chain_with_reidentified_reservation(
        created_at=changed_at,
        transitioned_at=changed_at,
    )
    with pytest.raises(ValidationError, match="reservation does not match approved risk sizing"):
        ValidatedExecutionChain.model_validate(content)


def test_valid_same_session_next_eligible_bar_is_selected() -> None:
    dataset, proposal, order = _session_selection_fixture(
        date(2024, 7, 2), include_same_session_candidate=True
    )
    selected = select_session_bounded_next_bar(proposal, order, dataset)
    assert selected.session_id == dataset.bars[0].session_id


def test_last_session_bar_absent_does_not_select_next_morning_open() -> None:
    dataset, proposal, order = _session_selection_fixture(
        date(2024, 7, 2),
        include_same_session_candidate=False,
        include_next_session_candidate=True,
    )
    with pytest.raises(ValueError, match="no eligible same-session"):
        select_session_bounded_next_bar(proposal, order, dataset)


def test_xnys_early_close_bounds_next_bar_without_hardcoded_time() -> None:
    dataset, proposal, order = _session_selection_fixture(
        date(2024, 7, 3),
        include_same_session_candidate=True,
        near_close=True,
    )
    selected = select_session_bounded_next_bar(proposal, order, dataset)
    session = UsEquitiesCalendar().session_for_date(date(2024, 7, 3))
    assert session is not None and session.early_close
    assert selected.end_at <= session.close_at


def test_xnys_dst_session_date_uses_authoritative_calendar_boundary() -> None:
    dataset, proposal, order = _session_selection_fixture(
        date(2024, 11, 4), include_same_session_candidate=True
    )
    selected = select_session_bounded_next_bar(proposal, order, dataset)
    session = UsEquitiesCalendar().session_for_date(date(2024, 11, 4))
    assert session is not None
    assert selected.session_id == session.session_id
    assert selected.end_at <= session.close_at


@pytest.mark.parametrize("mismatch", ["cost", "execution", "quantity", "side", "price", "bar"])
def test_execution_chain_rejects_cross_contract_mismatches(mismatch: str) -> None:
    chain = _valid_chain()
    content = chain.model_dump(mode="python")
    if mismatch == "cost":
        content["cost_configuration"] = cost_configuration(profile_version="v2")
    elif mismatch == "execution":
        content["execution_configuration"] = execution_configuration(routing_latency_seconds=1)
    elif mismatch == "quantity":
        content["order"] = _rebuild_order(chain.order, quantity=Decimal("0.2"))
    elif mismatch == "side":
        content["order"] = _rebuild_order(chain.order, side="SELL")
    elif mismatch == "price":
        wrong_price = chain.fill.fill_price + Decimal("1")
        content["fill"] = _rebuild_fill(
            chain.fill,
            fill_price=wrong_price,
            costs=calculate_fill_costs(chain.cost_configuration, chain.fill.quantity, wrong_price),
        )
    else:
        later = next(
            bar
            for bar in chain.dataset.bars
            if bar.start_at > chain.fill.execution_interval_start_at
        )
        market_content = chain.fill.market_event.model_dump(
            mode="python", exclude={"market_event_id"}
        )
        market_content.update(
            {
                "interval_start_at": later.start_at,
                "event_at": later.end_at,
                "available_at": later.available_at,
                "source_record_id": later.source_record_id,
            }
        )
        market = MarketEventReference.model_validate(
            {"market_event_id": calculate_market_event_id(market_content), **market_content}
        )
        content["fill"] = _rebuild_fill(
            chain.fill,
            market_event=market,
            fill_price=later.open,
            execution_interval_start_at=later.start_at,
            execution_interval_end_at=later.end_at,
            simulated_execution_at=later.start_at,
            fill_at=later.available_at,
            costs=calculate_fill_costs(chain.cost_configuration, chain.fill.quantity, later.open),
        )
    with pytest.raises(ValidationError):
        ValidatedExecutionChain.model_validate(content)
