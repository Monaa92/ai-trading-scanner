from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError
from simulation_helpers import digest, replay_event
from test_simulation_remediation_2 import (
    _open_artifact,
    _rebuild_artifact,
    _replace_final_portfolio,
    _resolution,
)

from ai_trading_scanner.domain import InstrumentId, TradeProposalId
from ai_trading_scanner.simulation import (
    CashLedgerSnapshot,
    MarketEventReference,
    PortfolioSnapshot,
    PositionChange,
    PositionSnapshot,
    ReplayArtifactBundle,
    ReplayPayloadKind,
    ReplayPhase,
    ResultFinalizationPayload,
    SimulationResult,
    calculate_marker_payload_id,
    calculate_market_event_id,
    calculate_portfolio_snapshot_id,
    calculate_position_change_id,
    calculate_position_id,
    calculate_replay_artifact_id,
    calculate_simulated_fill_id,
    calculate_simulated_order_id,
    order_replay_events,
    serialize_replay_events,
)
from ai_trading_scanner.simulation.models import SimulatedFill, SimulatedOrder


def _model_content(model: object, identity_field: str) -> dict[str, object]:
    return model.model_dump(mode="python", exclude={identity_field})  # type: ignore[attr-defined,no-any-return]


def _same_time_open_artifact() -> ReplayArtifactBundle:
    artifact = _open_artifact()
    final, finalization, events = _replace_final_portfolio(
        artifact, as_of=artifact.position_changes[0].changed_at
    )
    return _rebuild_artifact(
        artifact,
        events=events,
        portfolio_snapshots=(artifact.portfolio_snapshots[0], final),
        finalizations=(finalization,),
    )


def _two_instrument_same_time_artifact() -> ReplayArtifactBundle:
    first = _same_time_open_artifact()
    first_order = first.orders[0]
    first_fill = first.fills[0]
    first_change = first.position_changes[0]
    initial, first_final = first.portfolio_snapshots

    instrument = InstrumentId.parse("XNYS:MSFT")
    proposal_id = TradeProposalId.parse(digest("a"))
    order_content = _model_content(first_order, "order_id")
    order_content.update({"instrument_id": instrument, "proposal_id": proposal_id})
    second_order = SimulatedOrder.model_validate(
        {"order_id": calculate_simulated_order_id(order_content), **order_content}
    )

    market_content = _model_content(first_fill.market_event, "market_event_id")
    market_content.update(
        {"instrument_id": instrument, "source_record_id": "bar:second-instrument"}
    )
    second_market = MarketEventReference.model_validate(
        {"market_event_id": calculate_market_event_id(market_content), **market_content}
    )
    fill_content = _model_content(first_fill, "fill_id")
    fill_content.update(
        {
            "order_id": second_order.order_id,
            "proposal_id": proposal_id,
            "instrument_id": instrument,
            "market_event": second_market,
        }
    )
    second_fill = SimulatedFill.model_validate(
        {"fill_id": calculate_simulated_fill_id(fill_content), **fill_content}
    )
    second_resolution = _resolution(
        order_id=second_order.order_id,
        resolved_at=second_fill.fill_at,
        source_market_event_id=second_market.market_event_id,
    )
    second_position_id = calculate_position_id(
        second_order.run_id,
        second_order.account_id,
        second_order.allocation_id,
        second_order.agent_id,
        instrument,
        proposal_id,
    )
    change_content = _model_content(first_change, "position_change_id")
    change_content.update(
        {
            "position_id": second_position_id,
            "proposal_id": proposal_id,
            "order_id": second_order.order_id,
            "fill_id": second_fill.fill_id,
        }
    )
    second_change = PositionChange.model_validate(
        {"position_change_id": calculate_position_change_id(change_content), **change_content}
    )
    first_position = first_final.positions[0]
    position_content = first_position.model_dump(mode="python")
    position_content.update(
        {
            "position_id": second_position_id,
            "instrument_id": instrument,
            "opened_by_proposal_id": proposal_id,
        }
    )
    second_position = PositionSnapshot.model_validate(position_content)

    notional = first_fill.quantity * first_fill.fill_price
    total_costs = first_fill.costs.total + second_fill.costs.total
    cash = first.manifest.starting_capital - notional - first_fill.costs.total
    cash -= second_fill.quantity * second_fill.fill_price + second_fill.costs.total
    final_content: dict[str, object] = {
        "schema_version": "portfolio-snapshot-v1",
        "run_id": first.manifest.run_id,
        "account_id": first.manifest.account_id,
        "allocation_id": first.manifest.allocation_id,
        "agent_id": first.manifest.agent_id,
        "previous_snapshot_id": initial.portfolio_snapshot_id,
        "as_of": first_fill.fill_at,
        "starting_capital": first.manifest.starting_capital,
        "cash": CashLedgerSnapshot(
            currency=first.manifest.reporting_currency,
            available_cash=cash,
            reserved_cash=Decimal(0),
            committed_cash=Decimal(0),
            total_cash=cash,
        ),
        "positions": tuple(
            sorted((first_position, second_position), key=lambda item: str(item.position_id))
        ),
        "realized_gross_pnl": Decimal(0),
        "unrealized_gross_pnl": Decimal(0),
        "total_execution_costs": total_costs,
        "gross_trading_pnl": Decimal(0),
        "net_trading_pnl": -total_costs,
        "total_equity": first.manifest.starting_capital - total_costs,
    }
    final = PortfolioSnapshot.model_validate(
        {"portfolio_snapshot_id": calculate_portfolio_snapshot_id(final_content), **final_content}
    )
    finalization_content = _model_content(first.finalizations[0], "payload_id")
    finalization_content["final_portfolio_snapshot_id"] = final.portfolio_snapshot_id
    finalization = ResultFinalizationPayload.model_validate(
        {
            "payload_id": calculate_marker_payload_id(finalization_content),
            **finalization_content,
        }
    )
    removed = {str(first_final.portfolio_snapshot_id), first.finalizations[0].payload_id}
    events = tuple(event for event in first.events if event.payload_id not in removed)
    events += (
        replay_event(
            ReplayPhase.ORDER_SUBMISSION,
            second_order.submitted_at,
            payload_id=second_order.order_id,
        ),
        replay_event(
            ReplayPhase.EXECUTION_RESOLUTION,
            second_resolution.resolved_at,
            payload_id=second_resolution.payload_id,
        ),
        replay_event(ReplayPhase.FILL, second_fill.fill_at, payload_id=second_fill.fill_id),
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            second_change.changed_at,
            payload_kind=ReplayPayloadKind.POSITION_CHANGE,
            payload_id=second_change.position_change_id,
        ),
        replay_event(
            ReplayPhase.MARKET_DATA_AVAILABLE,
            second_market.available_at,
            payload_id=second_market.market_event_id,
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
        manifest=first.manifest,
        events=events,
        execution_resolutions=(*first.execution_resolutions, second_resolution),
        market_events=(*first.market_events, second_market),
        orders=(first_order, second_order),
        fills=(first_fill, second_fill),
        position_changes=(first_change, second_change),
        portfolio_snapshots=(initial, final),
        finalizations=(finalization,),
    )


def _artifact_content(artifact: ReplayArtifactBundle) -> dict[str, object]:
    return {
        name: getattr(artifact, name)
        for name in type(artifact).model_fields
        if name != "artifact_id"
    }


def test_equal_time_fill_application_and_checkpoint_follow_causal_order() -> None:
    artifact = _same_time_open_artifact()
    at = artifact.fills[0].fill_at
    same_time = [event.payload_kind for event in artifact.events if event.scheduled_at == at]
    assert same_time.index(ReplayPayloadKind.SIMULATED_FILL) < same_time.index(
        ReplayPayloadKind.POSITION_CHANGE
    )
    assert same_time.index(ReplayPayloadKind.POSITION_CHANGE) < same_time.index(
        ReplayPayloadKind.PORTFOLIO_SNAPSHOT
    )


def test_old_equal_time_snapshot_before_application_probe_fails_closed() -> None:
    artifact = _same_time_open_artifact()
    events = list(artifact.events)
    change_index = next(
        index
        for index, event in enumerate(events)
        if event.payload_kind is ReplayPayloadKind.POSITION_CHANGE
    )
    snapshot_index = next(
        index
        for index, event in enumerate(events)
        if event.payload_kind is ReplayPayloadKind.PORTFOLIO_SNAPSHOT
        and event.scheduled_at == artifact.position_changes[0].changed_at
    )
    events[change_index], events[snapshot_index] = events[snapshot_index], events[change_index]
    content = _artifact_content(artifact)
    content["events"] = tuple(events)
    with pytest.raises(ValidationError, match="events are not canonically ordered"):
        ReplayArtifactBundle.model_validate(
            {"artifact_id": calculate_replay_artifact_id(content), **content}
        )


def test_same_time_multiple_fills_and_instruments_have_deterministic_applications() -> None:
    artifact = _two_instrument_same_time_artifact()
    changes = tuple(
        event.payload_id
        for event in artifact.events
        if event.payload_kind is ReplayPayloadKind.POSITION_CHANGE
    )
    assert changes == tuple(sorted(changes))
    assert {position.instrument_id for position in artifact.portfolio_snapshots[-1].positions} == {
        InstrumentId.parse("XNYS:AAPL"),
        InstrumentId.parse("XNYS:MSFT"),
    }


def test_shuffled_order_insensitive_registries_produce_identical_artifact() -> None:
    artifact = _two_instrument_same_time_artifact()
    content = _artifact_content(artifact)
    for field in (
        "execution_resolutions",
        "market_events",
        "orders",
        "fills",
        "position_changes",
        "portfolio_snapshots",
    ):
        content[field] = tuple(reversed(cast(tuple[object, ...], content[field])))
    rebuilt = ReplayArtifactBundle.create(**content)
    assert rebuilt == artifact
    assert rebuilt.artifact_id == artifact.artifact_id


def test_duplicate_same_time_accounting_application_is_rejected() -> None:
    artifact = _same_time_open_artifact()
    content = _artifact_content(artifact)
    content["position_changes"] = (
        artifact.position_changes[0],
        artifact.position_changes[0],
    )
    with pytest.raises(ValidationError, match="one fill cannot be applied"):
        ReplayArtifactBundle.create(**content)


def test_same_time_checkpoint_with_only_one_of_two_applications_is_rejected() -> None:
    artifact = _two_instrument_same_time_artifact()
    one = _same_time_open_artifact().portfolio_snapshots[-1]
    one_content = one.model_dump(mode="python", exclude={"portfolio_snapshot_id"})
    one_content["previous_snapshot_id"] = artifact.portfolio_snapshots[0].portfolio_snapshot_id
    wrong = PortfolioSnapshot.model_validate(
        {"portfolio_snapshot_id": calculate_portfolio_snapshot_id(one_content), **one_content}
    )
    finalization_content = _model_content(artifact.finalizations[0], "payload_id")
    finalization_content["final_portfolio_snapshot_id"] = wrong.portfolio_snapshot_id
    finalization = ResultFinalizationPayload.model_validate(
        {
            "payload_id": calculate_marker_payload_id(finalization_content),
            **finalization_content,
        }
    )
    removed = {
        str(artifact.portfolio_snapshots[-1].portfolio_snapshot_id),
        artifact.finalizations[0].payload_id,
    }
    events = tuple(event for event in artifact.events if event.payload_id not in removed)
    events += (
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            wrong.as_of,
            payload_id=wrong.portfolio_snapshot_id,
        ),
        replay_event(
            ReplayPhase.RESULT_FINALIZATION,
            finalization.finalized_at,
            payload_id=finalization.payload_id,
        ),
    )
    content = _artifact_content(artifact)
    content.update(
        {
            "events": order_replay_events(events),
            "portfolio_snapshots": (artifact.portfolio_snapshots[0], wrong),
            "finalizations": (finalization,),
        }
    )
    with pytest.raises(ValidationError, match="derived chronological accounting"):
        ReplayArtifactBundle.create(**content)


def test_phase_precedence_wins_at_identical_timestamp() -> None:
    artifact = _same_time_open_artifact()
    at = artifact.fills[0].fill_at
    phases = [event.phase for event in artifact.events if event.scheduled_at == at]
    assert phases == sorted(phases)
    assert phases.index(ReplayPhase.FILL) < phases.index(ReplayPhase.PORTFOLIO_UPDATE)
    assert phases.index(ReplayPhase.PORTFOLIO_UPDATE) < phases.index(
        ReplayPhase.MARKET_DATA_AVAILABLE
    )


def test_repeated_shuffled_run_has_identical_bytes_and_result_identity() -> None:
    artifact = _two_instrument_same_time_artifact()
    content = _artifact_content(artifact)
    content["events"] = tuple(reversed(artifact.events))
    content["fills"] = tuple(reversed(artifact.fills))
    content["position_changes"] = tuple(reversed(artifact.position_changes))
    repeated = ReplayArtifactBundle.create(**content)
    assert serialize_replay_events(repeated.events) == serialize_replay_events(artifact.events)
    assert repeated.artifact_id == artifact.artifact_id
    assert (
        SimulationResult.create(repeated).result_id == SimulationResult.create(artifact).result_id
    )


def test_genuinely_different_registry_content_changes_identity() -> None:
    artifact = _two_instrument_same_time_artifact()
    assert artifact.artifact_id != _same_time_open_artifact().artifact_id
