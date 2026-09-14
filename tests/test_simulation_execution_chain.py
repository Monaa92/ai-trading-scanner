from __future__ import annotations

import hashlib
from datetime import UTC, datetime
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
    QualityStatus,
    Timeframe,
)
from ai_trading_scanner.risk import RiskEngine
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


def test_valid_chain_enforces_zero_latency_and_canonical_next_open() -> None:
    chain = _valid_chain()
    assert chain.order.eligible_at == chain.order.submitted_at
    assert chain.fill.fill_price == next(
        bar.open
        for bar in chain.dataset.bars
        if bar.start_at == chain.fill.execution_interval_start_at
    )


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
