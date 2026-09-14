from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from simulation_helpers import (
    cost_configuration,
    digest,
    initial_portfolio,
    market_event,
    minimal_replay_artifact,
    replay_event,
    run_manifest,
    simulated_fill,
    simulated_order,
)

from ai_trading_scanner.domain import SimulatedFillId, SimulatedOrderId
from ai_trading_scanner.simulation import (
    CashLedgerSnapshot,
    ExecutionResolutionOutcome,
    ExecutionResolutionPayload,
    ExecutionResolutionReason,
    PortfolioSnapshot,
    PositionChange,
    PositionChangeKind,
    PositionSnapshot,
    RealizedTradeResult,
    ReplayArtifactBundle,
    ReplayPayloadKind,
    ReplayPhase,
    ResultFinalizationPayload,
    SimulatedFill,
    SimulationResultStatus,
    calculate_fill_costs,
    calculate_marker_payload_id,
    calculate_portfolio_snapshot_id,
    calculate_position_change_id,
    calculate_position_id,
    calculate_realized_trade_result_id,
    calculate_replay_artifact_id,
    calculate_simulated_fill_id,
    order_replay_events,
)


def _resolution(
    *,
    order_id: SimulatedOrderId,
    resolved_at: object,
    outcome: ExecutionResolutionOutcome = ExecutionResolutionOutcome.FILL_READY,
    source_market_event_id: object | None,
    reason: ExecutionResolutionReason | None = None,
) -> ExecutionResolutionPayload:
    content: dict[str, object] = {
        "schema_version": "execution-resolution-payload-v2",
        "run_id": simulated_order().run_id,
        "order_id": order_id,
        "resolved_at": resolved_at,
        "outcome": outcome,
        "reason": reason,
        "source_market_event_id": source_market_event_id,
    }
    return ExecutionResolutionPayload.model_validate(
        {"payload_id": calculate_marker_payload_id(content), **content}
    )


def _open_artifact() -> ReplayArtifactBundle:
    starting = initial_portfolio()
    order = simulated_order(quantity="0.1")
    source = market_event()
    quantity = Decimal("0.1")
    costs = calculate_fill_costs(cost_configuration(), quantity, Decimal("100"))
    fill = simulated_fill(
        order_id=order.order_id,
        quantity=quantity,
        costs=costs,
    )
    resolution = _resolution(
        order_id=order.order_id,
        resolved_at=fill.fill_at,
        source_market_event_id=source.market_event_id,
    )
    position_id = calculate_position_id(
        order.run_id,
        order.account_id,
        order.allocation_id,
        order.agent_id,
        order.instrument_id,
        order.proposal_id,
    )
    change_content: dict[str, object] = {
        "schema_version": "position-change-v1",
        "run_id": order.run_id,
        "account_id": order.account_id,
        "allocation_id": order.allocation_id,
        "agent_id": order.agent_id,
        "position_id": position_id,
        "proposal_id": order.proposal_id,
        "order_id": order.order_id,
        "fill_id": fill.fill_id,
        "management_mandate_id": order.management_mandate_id,
        "kind": PositionChangeKind.OPEN,
        "previous_quantity": Decimal(0),
        "quantity_delta": quantity,
        "new_quantity": quantity,
        "changed_at": fill.fill_at,
    }
    change = PositionChange.model_validate(
        {"position_change_id": calculate_position_change_id(change_content), **change_content}
    )
    position = PositionSnapshot(
        position_id=position_id,
        run_id=order.run_id,
        account_id=order.account_id,
        allocation_id=order.allocation_id,
        agent_id=order.agent_id,
        strategy_id=order.strategy_id,
        management_mandate_id=order.management_mandate_id,
        instrument_id=order.instrument_id,
        opened_by_proposal_id=order.proposal_id,
        currency=order.currency,
        opened_at=fill.fill_at,
        marked_at=fill.fill_at,
        quantity=quantity,
        average_entry_price=fill.fill_price,
        mark_price=fill.fill_price,
        gross_cost_basis=Decimal("10"),
        market_value=Decimal("10"),
        unrealized_gross_pnl=Decimal(0),
    )
    cash = Decimal("50") - Decimal("10") - costs.total
    final_content: dict[str, object] = {
        "schema_version": "portfolio-snapshot-v1",
        "run_id": order.run_id,
        "account_id": order.account_id,
        "allocation_id": order.allocation_id,
        "agent_id": order.agent_id,
        "previous_snapshot_id": starting.portfolio_snapshot_id,
        "as_of": fill.fill_at + timedelta(microseconds=1),
        "starting_capital": Decimal("50"),
        "cash": CashLedgerSnapshot(
            currency="USD",
            available_cash=cash,
            reserved_cash=Decimal(0),
            committed_cash=Decimal(0),
            total_cash=cash,
        ),
        "positions": (position,),
        "realized_gross_pnl": Decimal(0),
        "unrealized_gross_pnl": Decimal(0),
        "total_execution_costs": costs.total,
        "gross_trading_pnl": Decimal(0),
        "net_trading_pnl": -costs.total,
        "total_equity": Decimal("50") - costs.total,
    }
    final = PortfolioSnapshot.model_validate(
        {"portfolio_snapshot_id": calculate_portfolio_snapshot_id(final_content), **final_content}
    )
    finalization_content: dict[str, object] = {
        "schema_version": "result-finalization-payload-v1",
        "run_id": order.run_id,
        "status": SimulationResultStatus.COMPLETE,
        "final_portfolio_snapshot_id": final.portfolio_snapshot_id,
        "realized_trade_result_ids": (),
        "finalized_at": final.as_of + timedelta(seconds=1),
    }
    finalization = ResultFinalizationPayload.model_validate(
        {
            "payload_id": calculate_marker_payload_id(finalization_content),
            **finalization_content,
        }
    )
    events = (
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            starting.as_of,
            payload_id=starting.portfolio_snapshot_id,
        ),
        replay_event(ReplayPhase.ORDER_SUBMISSION, order.submitted_at, payload_id=order.order_id),
        replay_event(
            ReplayPhase.EXECUTION_RESOLUTION,
            resolution.resolved_at,
            payload_id=resolution.payload_id,
        ),
        replay_event(ReplayPhase.FILL, fill.fill_at, payload_id=fill.fill_id),
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            change.changed_at,
            payload_kind=ReplayPayloadKind.POSITION_CHANGE,
            payload_id=change.position_change_id,
        ),
        replay_event(
            ReplayPhase.MARKET_DATA_AVAILABLE,
            source.available_at,
            payload_id=source.market_event_id,
        ),
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            final.as_of,
            payload_id=final.portfolio_snapshot_id,
        ),
        replay_event(
            ReplayPhase.RESULT_FINALIZATION,
            finalization.finalized_at,
            payload_id=finalization.payload_id,
        ),
    )
    return ReplayArtifactBundle.create(
        manifest=run_manifest(),
        events=events,
        execution_resolutions=(resolution,),
        market_events=(source,),
        orders=(order,),
        fills=(fill,),
        position_changes=(change,),
        portfolio_snapshots=(starting, final),
        finalizations=(finalization,),
    )


def _closed_artifact() -> ReplayArtifactBundle:
    open_artifact = _open_artifact()
    starting, open_snapshot = open_artifact.portfolio_snapshots
    entry_order = open_artifact.orders[0]
    entry_fill = open_artifact.fills[0]
    entry_change = open_artifact.position_changes[0]
    exit_source = market_event(
        interval_start_at=entry_fill.execution_interval_end_at + timedelta(minutes=1),
        event_at=entry_fill.execution_interval_end_at + timedelta(minutes=2),
        available_at=entry_fill.execution_interval_end_at + timedelta(minutes=2, seconds=2),
        source_record_id="bar:exit",
    )
    exit_order = simulated_order(
        proposal_id=entry_order.proposal_id,
        strategy_decision_id=entry_order.strategy_decision_id,
        risk_decision_id=entry_order.risk_decision_id,
        reservation_id=entry_order.reservation_id,
        side="SELL",
        quantity=entry_order.quantity,
        decision_at=open_snapshot.as_of,
        submitted_at=open_snapshot.as_of,
        eligible_at=open_snapshot.as_of,
        valid_until=open_snapshot.as_of + timedelta(minutes=10),
    )
    exit_costs = calculate_fill_costs(cost_configuration(), exit_order.quantity, Decimal("110"))
    exit_fill = simulated_fill(
        order_id=exit_order.order_id,
        proposal_id=exit_order.proposal_id,
        risk_decision_id=exit_order.risk_decision_id,
        reservation_id=exit_order.reservation_id,
        side=exit_order.side,
        quantity=exit_order.quantity,
        fill_price=Decimal("110"),
        market_event=exit_source,
        submitted_at=exit_order.submitted_at,
        eligible_at=exit_order.eligible_at,
        execution_interval_start_at=exit_source.interval_start_at,
        execution_interval_end_at=exit_source.event_at,
        simulated_execution_at=exit_source.interval_start_at,
        fill_at=exit_source.available_at,
        costs=exit_costs,
    )
    exit_resolution = _resolution(
        order_id=exit_order.order_id,
        resolved_at=exit_fill.fill_at,
        source_market_event_id=exit_source.market_event_id,
    )
    close_content: dict[str, object] = {
        "schema_version": "position-change-v1",
        "run_id": exit_order.run_id,
        "account_id": exit_order.account_id,
        "allocation_id": exit_order.allocation_id,
        "agent_id": exit_order.agent_id,
        "position_id": entry_change.position_id,
        "proposal_id": exit_order.proposal_id,
        "order_id": exit_order.order_id,
        "fill_id": exit_fill.fill_id,
        "management_mandate_id": exit_order.management_mandate_id,
        "kind": PositionChangeKind.CLOSE,
        "previous_quantity": entry_fill.quantity,
        "quantity_delta": -exit_fill.quantity,
        "new_quantity": Decimal(0),
        "changed_at": exit_fill.fill_at,
    }
    close = PositionChange.model_validate(
        {"position_change_id": calculate_position_change_id(close_content), **close_content}
    )
    total_costs = entry_fill.costs.total + exit_fill.costs.total
    gross = exit_fill.quantity * (exit_fill.fill_price - entry_fill.fill_price)
    trade_content: dict[str, object] = {
        "schema_version": "realized-trade-result-v1",
        "run_id": exit_order.run_id,
        "account_id": exit_order.account_id,
        "allocation_id": exit_order.allocation_id,
        "agent_id": exit_order.agent_id,
        "strategy_id": exit_order.strategy_id,
        "management_mandate_id": exit_order.management_mandate_id,
        "position_id": entry_change.position_id,
        "proposal_id": entry_order.proposal_id,
        "entry_fill_ids": (entry_fill.fill_id,),
        "exit_fill_ids": (exit_fill.fill_id,),
        "opened_at": entry_fill.fill_at,
        "closed_at": exit_fill.fill_at,
        "quantity": entry_fill.quantity,
        "gross_pnl": gross,
        "total_execution_costs": total_costs,
        "net_pnl": gross - total_costs,
    }
    trade = RealizedTradeResult.model_validate(
        {
            "realized_trade_result_id": calculate_realized_trade_result_id(trade_content),
            **trade_content,
        }
    )
    cash = Decimal("50") + gross - total_costs
    final_content: dict[str, object] = {
        "schema_version": "portfolio-snapshot-v1",
        "run_id": exit_order.run_id,
        "account_id": exit_order.account_id,
        "allocation_id": exit_order.allocation_id,
        "agent_id": exit_order.agent_id,
        "previous_snapshot_id": open_snapshot.portfolio_snapshot_id,
        "as_of": exit_fill.fill_at + timedelta(microseconds=1),
        "starting_capital": Decimal("50"),
        "cash": CashLedgerSnapshot(
            currency="USD",
            available_cash=cash,
            reserved_cash=Decimal(0),
            committed_cash=Decimal(0),
            total_cash=cash,
        ),
        "positions": (),
        "realized_gross_pnl": gross,
        "unrealized_gross_pnl": Decimal(0),
        "total_execution_costs": total_costs,
        "gross_trading_pnl": gross,
        "net_trading_pnl": gross - total_costs,
        "total_equity": cash,
    }
    final = PortfolioSnapshot.model_validate(
        {"portfolio_snapshot_id": calculate_portfolio_snapshot_id(final_content), **final_content}
    )
    finalization_content: dict[str, object] = {
        "schema_version": "result-finalization-payload-v1",
        "run_id": exit_order.run_id,
        "status": SimulationResultStatus.COMPLETE,
        "final_portfolio_snapshot_id": final.portfolio_snapshot_id,
        "realized_trade_result_ids": (trade.realized_trade_result_id,),
        "finalized_at": final.as_of + timedelta(seconds=1),
    }
    finalization = ResultFinalizationPayload.model_validate(
        {
            "payload_id": calculate_marker_payload_id(finalization_content),
            **finalization_content,
        }
    )
    payloads = (
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            starting.as_of,
            payload_id=starting.portfolio_snapshot_id,
        ),
        *(
            replay_event(
                ReplayPhase.ORDER_SUBMISSION, order.submitted_at, payload_id=order.order_id
            )
            for order in (entry_order, exit_order)
        ),
        *(
            replay_event(
                ReplayPhase.EXECUTION_RESOLUTION,
                resolution.resolved_at,
                payload_id=resolution.payload_id,
            )
            for resolution in (*open_artifact.execution_resolutions, exit_resolution)
        ),
        *(
            replay_event(ReplayPhase.FILL, fill.fill_at, payload_id=fill.fill_id)
            for fill in (entry_fill, exit_fill)
        ),
        *(
            replay_event(
                ReplayPhase.PORTFOLIO_UPDATE,
                change.changed_at,
                payload_kind=ReplayPayloadKind.POSITION_CHANGE,
                payload_id=change.position_change_id,
            )
            for change in (entry_change, close)
        ),
        *(
            replay_event(
                ReplayPhase.MARKET_DATA_AVAILABLE,
                source.available_at,
                payload_id=source.market_event_id,
            )
            for source in (*open_artifact.market_events, exit_source)
        ),
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            open_snapshot.as_of,
            payload_id=open_snapshot.portfolio_snapshot_id,
        ),
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            trade.closed_at,
            payload_kind=ReplayPayloadKind.REALIZED_TRADE,
            payload_id=trade.realized_trade_result_id,
        ),
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            final.as_of,
            payload_id=final.portfolio_snapshot_id,
        ),
        replay_event(
            ReplayPhase.RESULT_FINALIZATION,
            finalization.finalized_at,
            payload_id=finalization.payload_id,
        ),
    )
    return ReplayArtifactBundle.create(
        manifest=open_artifact.manifest,
        events=payloads,
        execution_resolutions=(*open_artifact.execution_resolutions, exit_resolution),
        market_events=(*open_artifact.market_events, exit_source),
        orders=(entry_order, exit_order),
        fills=(entry_fill, exit_fill),
        position_changes=(entry_change, close),
        portfolio_snapshots=(starting, open_snapshot, final),
        realized_trades=(trade,),
        finalizations=(finalization,),
    )


def _rebuild_artifact(artifact: ReplayArtifactBundle, **changes: object) -> ReplayArtifactBundle:
    content = artifact.model_dump(mode="python", exclude={"artifact_id"})
    content.update(changes)
    return ReplayArtifactBundle.model_validate(
        {"artifact_id": calculate_replay_artifact_id(content), **content}
    )


def _replace_final_portfolio(
    artifact: ReplayArtifactBundle, **changes: object
) -> tuple[PortfolioSnapshot, ResultFinalizationPayload, tuple[object, ...]]:
    final = artifact.portfolio_snapshots[-1]
    content = final.model_dump(mode="python", exclude={"portfolio_snapshot_id"})
    content.update(changes)
    replacement = PortfolioSnapshot.model_validate(
        {"portfolio_snapshot_id": calculate_portfolio_snapshot_id(content), **content}
    )
    finalization_content = artifact.finalizations[0].model_dump(
        mode="python", exclude={"payload_id"}
    )
    finalization_content["final_portfolio_snapshot_id"] = replacement.portfolio_snapshot_id
    finalization = ResultFinalizationPayload.model_validate(
        {
            "payload_id": calculate_marker_payload_id(finalization_content),
            **finalization_content,
        }
    )
    events = (
        *tuple(
            event
            for event in artifact.events
            if event.payload_id
            not in {str(final.portfolio_snapshot_id), artifact.finalizations[0].payload_id}
        ),
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            replacement.as_of,
            payload_id=replacement.portfolio_snapshot_id,
        ),
        replay_event(
            ReplayPhase.RESULT_FINALIZATION,
            finalization.finalized_at,
            payload_id=finalization.payload_id,
        ),
    )
    return replacement, finalization, order_replay_events(events)


def test_fully_reconciled_chronological_complete_chain_is_accepted() -> None:
    artifact = _open_artifact()
    assert artifact.finalizations[0].status is SimulationResultStatus.COMPLETE


def test_fully_reconciled_closed_trade_lifecycle_is_accepted() -> None:
    artifact = _closed_artifact()
    assert len(artifact.realized_trades) == 1
    assert artifact.portfolio_snapshots[-1].positions == ()


def test_complete_rejects_incorrect_realized_pnl() -> None:
    artifact = _closed_artifact()
    original = artifact.realized_trades[0]
    trade_content = original.model_dump(mode="python", exclude={"realized_trade_result_id"})
    trade_content["gross_pnl"] = original.gross_pnl + Decimal("1")
    trade_content["net_pnl"] = trade_content["gross_pnl"] - original.total_execution_costs
    forged = RealizedTradeResult.model_validate(
        {
            "realized_trade_result_id": calculate_realized_trade_result_id(trade_content),
            **trade_content,
        }
    )
    finalization_content = artifact.finalizations[0].model_dump(
        mode="python", exclude={"payload_id"}
    )
    finalization_content["realized_trade_result_ids"] = (forged.realized_trade_result_id,)
    finalization = ResultFinalizationPayload.model_validate(
        {
            "payload_id": calculate_marker_payload_id(finalization_content),
            **finalization_content,
        }
    )
    events = (
        *tuple(
            event
            for event in artifact.events
            if event.payload_id
            not in {str(original.realized_trade_result_id), artifact.finalizations[0].payload_id}
        ),
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            forged.closed_at,
            payload_kind=ReplayPayloadKind.REALIZED_TRADE,
            payload_id=forged.realized_trade_result_id,
        ),
        replay_event(
            ReplayPhase.RESULT_FINALIZATION,
            finalization.finalized_at,
            payload_id=finalization.payload_id,
        ),
    )
    with pytest.raises(ValidationError, match="realized trades differ"):
        _rebuild_artifact(
            artifact,
            events=order_replay_events(events),
            realized_trades=(forged,),
            finalizations=(finalization,),
        )


def _assert_fabricated_final_rejected(portfolio_changes: dict[str, object]) -> None:
    artifact = _open_artifact()
    final, finalization, events = _replace_final_portfolio(artifact, **portfolio_changes)
    with pytest.raises(ValidationError, match="derived chronological accounting"):
        _rebuild_artifact(
            artifact,
            events=events,
            portfolio_snapshots=(artifact.portfolio_snapshots[0], final),
            finalizations=(finalization,),
        )


def test_complete_rejects_valid_fill_with_unchanged_final_cash_and_missing_position() -> None:
    _assert_fabricated_final_rejected(
        {
            "cash": CashLedgerSnapshot(
                currency="USD",
                available_cash=Decimal("50"),
                reserved_cash=Decimal(0),
                committed_cash=Decimal(0),
                total_cash=Decimal("50"),
            ),
            "positions": (),
            "total_execution_costs": Decimal(0),
            "net_trading_pnl": Decimal(0),
            "total_equity": Decimal("50"),
        }
    )


def test_complete_rejects_execution_costs_omitted_from_final_portfolio() -> None:
    _assert_fabricated_final_rejected(
        {
            "cash": CashLedgerSnapshot(
                currency="USD",
                available_cash=Decimal("40"),
                reserved_cash=Decimal(0),
                committed_cash=Decimal(0),
                total_cash=Decimal("40"),
            ),
            "total_execution_costs": Decimal(0),
            "net_trading_pnl": Decimal(0),
            "total_equity": Decimal("50"),
        }
    )


def test_complete_rejects_incorrect_net_pnl_and_final_equity() -> None:
    _assert_fabricated_final_rejected(
        {
            "cash": CashLedgerSnapshot(
                currency="USD",
                available_cash=Decimal("39.8"),
                reserved_cash=Decimal(0),
                committed_cash=Decimal(0),
                total_cash=Decimal("39.8"),
            ),
            "total_execution_costs": Decimal("0.2"),
            "net_trading_pnl": Decimal("-0.2"),
            "total_equity": Decimal("49.8"),
        }
    )


def test_complete_rejects_incorrect_final_equity_projection() -> None:
    _assert_fabricated_final_rejected(
        {
            "cash": CashLedgerSnapshot(
                currency="USD",
                available_cash=Decimal("39.7"),
                reserved_cash=Decimal(0),
                committed_cash=Decimal(0),
                total_cash=Decimal("39.7"),
            ),
            "total_execution_costs": Decimal("0.3"),
            "net_trading_pnl": Decimal("-0.3"),
            "total_equity": Decimal("49.7"),
        }
    )


def test_complete_rejects_one_fill_applied_twice() -> None:
    artifact = _open_artifact()
    original = artifact.position_changes[0]
    content = original.model_dump(mode="python", exclude={"position_change_id"})
    content["management_mandate_id"] = digest("7")
    duplicate = PositionChange.model_validate(
        {"position_change_id": calculate_position_change_id(content), **content}
    )
    event = replay_event(
        ReplayPhase.PORTFOLIO_UPDATE,
        duplicate.changed_at,
        payload_kind=ReplayPayloadKind.POSITION_CHANGE,
        payload_id=duplicate.position_change_id,
    )
    with pytest.raises(ValidationError, match="foreign or unrelated fill"):
        _rebuild_artifact(
            artifact,
            events=order_replay_events((*artifact.events, event)),
            position_changes=(original, duplicate),
        )


def test_complete_rejects_foreign_fill_position_application() -> None:
    artifact = _open_artifact()
    original = artifact.position_changes[0]
    content = original.model_dump(mode="python", exclude={"position_change_id"})
    content["fill_id"] = SimulatedFillId.parse(digest("7"))
    foreign = PositionChange.model_validate(
        {"position_change_id": calculate_position_change_id(content), **content}
    )
    events = (
        *tuple(
            event
            for event in artifact.events
            if event.payload_id != str(original.position_change_id)
        ),
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            foreign.changed_at,
            payload_kind=ReplayPayloadKind.POSITION_CHANGE,
            payload_id=foreign.position_change_id,
        ),
    )
    with pytest.raises(ValidationError, match="missing fill or order"):
        _rebuild_artifact(
            artifact,
            events=order_replay_events(events),
            position_changes=(foreign,),
        )


def test_complete_rejects_missing_fill_application() -> None:
    artifact = _open_artifact()
    change = artifact.position_changes[0]
    events = tuple(
        event for event in artifact.events if event.payload_id != str(change.position_change_id)
    )
    with pytest.raises(ValidationError, match="exactly one application per fill"):
        _rebuild_artifact(
            artifact,
            events=events,
            position_changes=(),
        )


def _replace_resolution_events(
    artifact: ReplayArtifactBundle, resolutions: tuple[ExecutionResolutionPayload, ...]
) -> tuple[object, ...]:
    old_ids = {item.payload_id for item in artifact.execution_resolutions}
    retained = tuple(event for event in artifact.events if event.payload_id not in old_ids)
    added = tuple(
        replay_event(
            ReplayPhase.EXECUTION_RESOLUTION,
            resolution.resolved_at,
            payload_id=resolution.payload_id,
        )
        for resolution in resolutions
    )
    return order_replay_events((*retained, *added))


def test_resolution_rejects_nonexistent_order() -> None:
    artifact = _open_artifact()
    resolution = _resolution(
        order_id=SimulatedOrderId.parse(digest("7")),
        resolved_at=artifact.fills[0].fill_at,
        source_market_event_id=artifact.market_events[0].market_event_id,
    )
    with pytest.raises(ValidationError, match="missing simulated order"):
        _rebuild_artifact(
            artifact,
            events=_replace_resolution_events(artifact, (resolution,)),
            execution_resolutions=(resolution,),
        )


def test_fill_ready_resolution_rejects_nonexistent_market_event() -> None:
    artifact = _open_artifact()
    resolution = _resolution(
        order_id=artifact.orders[0].order_id,
        resolved_at=artifact.fills[0].fill_at,
        source_market_event_id=digest("7"),
    )
    with pytest.raises(ValidationError, match="missing market event"):
        _rebuild_artifact(
            artifact,
            events=_replace_resolution_events(artifact, (resolution,)),
            execution_resolutions=(resolution,),
        )


def test_fill_ready_resolution_without_fill_is_rejected() -> None:
    artifact = _open_artifact()
    fill = artifact.fills[0]
    change = artifact.position_changes[0]
    events = tuple(
        event
        for event in artifact.events
        if event.payload_id not in {str(fill.fill_id), str(change.position_change_id)}
    )
    with pytest.raises(ValidationError, match="requires exactly one matching fill"):
        _rebuild_artifact(
            artifact,
            events=events,
            fills=(),
            position_changes=(),
        )


def test_fill_ready_resolution_with_multiple_fills_is_rejected() -> None:
    artifact = _open_artifact()
    original = artifact.fills[0]
    content = original.model_dump(mode="python", exclude={"fill_id"})
    content["fill_at"] = original.fill_at + timedelta(microseconds=1)
    duplicate = SimulatedFill.model_validate(
        {"fill_id": calculate_simulated_fill_id(content), **content}
    )
    event = replay_event(ReplayPhase.FILL, duplicate.fill_at, payload_id=duplicate.fill_id)
    with pytest.raises(ValidationError, match="requires exactly one matching fill"):
        _rebuild_artifact(
            artifact,
            events=order_replay_events((*artifact.events, event)),
            fills=(original, duplicate),
        )


def test_unfilled_terminal_resolution_with_fill_is_rejected() -> None:
    artifact = _open_artifact()
    order = artifact.orders[0]
    resolution = _resolution(
        order_id=order.order_id,
        resolved_at=order.valid_until,
        outcome=ExecutionResolutionOutcome.EXPIRED_UNFILLED,
        reason=ExecutionResolutionReason.ORDER_VALIDITY_EXPIRED,
        source_market_event_id=None,
    )
    with pytest.raises(ValidationError, match="cannot have a fill"):
        _rebuild_artifact(
            artifact,
            events=_replace_resolution_events(artifact, (resolution,)),
            execution_resolutions=(resolution,),
        )


def test_two_terminal_resolutions_for_one_order_are_rejected() -> None:
    artifact = _open_artifact()
    order = artifact.orders[0]
    second = _resolution(
        order_id=order.order_id,
        resolved_at=order.valid_until,
        outcome=ExecutionResolutionOutcome.EXPIRED_UNFILLED,
        reason=ExecutionResolutionReason.ORDER_VALIDITY_EXPIRED,
        source_market_event_id=None,
    )
    resolutions = (artifact.execution_resolutions[0], second)
    with pytest.raises(ValidationError, match="multiple terminal"):
        _rebuild_artifact(
            artifact,
            events=_replace_resolution_events(artifact, resolutions),
            execution_resolutions=resolutions,
        )


def test_unfilled_resolution_requires_outcome_specific_reason() -> None:
    order = simulated_order()
    with pytest.raises(ValidationError, match="outcome and reason"):
        _resolution(
            order_id=order.order_id,
            resolved_at=order.valid_until,
            outcome=ExecutionResolutionOutcome.EXPIRED_UNFILLED,
            reason=ExecutionResolutionReason.NO_ELIGIBLE_SAME_SESSION_BAR,
            source_market_event_id=None,
        )


def test_valid_no_eligible_data_terminal_resolution_is_accepted_for_incomplete_run() -> None:
    artifact = minimal_replay_artifact(status=SimulationResultStatus.INCOMPLETE)
    order = simulated_order()
    resolution = _resolution(
        order_id=order.order_id,
        resolved_at=order.valid_until,
        outcome=ExecutionResolutionOutcome.NO_ELIGIBLE_DATA,
        reason=ExecutionResolutionReason.NO_ELIGIBLE_SAME_SESSION_BAR,
        source_market_event_id=None,
    )
    events = order_replay_events(
        (
            *artifact.events[:-1],
            replay_event(
                ReplayPhase.ORDER_SUBMISSION,
                order.submitted_at,
                payload_id=order.order_id,
            ),
            replay_event(
                ReplayPhase.EXECUTION_RESOLUTION,
                resolution.resolved_at,
                payload_id=resolution.payload_id,
            ),
            artifact.events[-1],
        )
    )
    rebuilt = _rebuild_artifact(
        artifact,
        events=events,
        orders=(order,),
        execution_resolutions=(resolution,),
    )
    assert rebuilt.execution_resolutions == (resolution,)
