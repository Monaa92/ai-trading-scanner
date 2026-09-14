from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from simulation_helpers import (
    BASE,
    digest,
    execution_configuration,
    initial_portfolio,
    market_event,
    minimal_replay_artifact,
    replay_event,
    run_manifest,
    simulated_fill,
    simulated_order,
)

from ai_trading_scanner.domain import InstrumentId, SimulatedFillId, TradeProposalId
from ai_trading_scanner.domain.content_identity import canonical_json_bytes_v2
from ai_trading_scanner.simulation import (
    RealizedTradeResult,
    ReplayArtifactBundle,
    ReplayPayloadKind,
    ReplayPhase,
    ResultFinalizationPayload,
    SimulationResult,
    SimulationResultStatus,
    calculate_marker_payload_id,
    calculate_position_id,
    calculate_realized_trade_result_id,
    calculate_replay_artifact_id,
    calculate_simulation_result_id,
    order_replay_events,
    serialize_replay_events,
)


def _validate_changed_artifact(
    artifact: ReplayArtifactBundle, **changes: object
) -> ReplayArtifactBundle:
    content = artifact.model_dump(mode="python", exclude={"artifact_id"})
    content.update(changes)
    return ReplayArtifactBundle.model_validate(
        {"artifact_id": calculate_replay_artifact_id(content), **content}
    )


def _finalization(
    artifact: ReplayArtifactBundle,
    *,
    portfolio_id: object | None = None,
    trade_ids: tuple[object, ...] = (),
) -> ResultFinalizationPayload:
    content: dict[str, object] = {
        "schema_version": "result-finalization-payload-v1",
        "run_id": artifact.manifest.run_id,
        "status": SimulationResultStatus.COMPLETE,
        "final_portfolio_snapshot_id": portfolio_id
        or artifact.portfolio_snapshots[0].portfolio_snapshot_id,
        "realized_trade_result_ids": trade_ids,
        "finalized_at": artifact.finalizations[0].finalized_at,
    }
    return ResultFinalizationPayload.model_validate(
        {"payload_id": calculate_marker_payload_id(content), **content}
    )


@pytest.mark.parametrize(
    "values",
    [
        (Decimal("1"), Decimal("1.0"), Decimal("1.00"), Decimal("10E-1")),
        (Decimal("0"), Decimal("0.0"), Decimal("-0")),
        (Decimal("1000"), Decimal("1E+3"), Decimal("10E+2")),
    ],
)
def test_v2_decimal_canonicalization_collapses_equivalent_values(
    values: tuple[Decimal, ...],
) -> None:
    assert len({canonical_json_bytes_v2({"value": value}) for value in values}) == 1


def test_decimal_scale_does_not_change_phase6_contract_identities() -> None:
    assert execution_configuration(quantity_increment="1").execution_model_id == (
        execution_configuration(quantity_increment="1.00").execution_model_id
    )
    assert (
        run_manifest(starting_capital="50").run_id == run_manifest(starting_capital="50.000").run_id
    )
    assert simulated_order(quantity="1").order_id == simulated_order(quantity="1.0").order_id


def test_replay_artifact_rejects_missing_payload_reference() -> None:
    artifact = minimal_replay_artifact()
    missing = replay_event(
        ReplayPhase.MARKET_DATA_AVAILABLE,
        BASE + timedelta(seconds=1),
        payload_id=digest("7"),
    )
    events = order_replay_events((*artifact.events[:-1], missing, artifact.events[-1]))
    with pytest.raises(ValidationError, match="missing or unreferenced"):
        _validate_changed_artifact(artifact, events=events)


def test_replay_artifact_rejects_foreign_final_portfolio() -> None:
    artifact = minimal_replay_artifact()
    foreign = initial_portfolio(run_id=run_manifest(strategy_version="foreign").run_id)
    finalization = _finalization(artifact, portfolio_id=foreign.portfolio_snapshot_id)
    events = order_replay_events(
        (
            replay_event(
                ReplayPhase.PORTFOLIO_UPDATE,
                foreign.as_of,
                payload_id=foreign.portfolio_snapshot_id,
            ),
            replay_event(
                ReplayPhase.RESULT_FINALIZATION,
                finalization.finalized_at,
                payload_id=finalization.payload_id,
            ),
        )
    )
    with pytest.raises(ValidationError, match="run or ownership"):
        _validate_changed_artifact(
            artifact,
            events=events,
            portfolio_snapshots=(foreign,),
            finalizations=(finalization,),
        )


def test_replay_artifact_rejects_foreign_realized_trade() -> None:
    artifact = minimal_replay_artifact()
    foreign_manifest = run_manifest(strategy_version="foreign")
    proposal_id = TradeProposalId.parse(digest("1"))
    trade_content: dict[str, object] = {
        "schema_version": "realized-trade-result-v1",
        "run_id": foreign_manifest.run_id,
        "account_id": foreign_manifest.account_id,
        "allocation_id": foreign_manifest.allocation_id,
        "agent_id": foreign_manifest.agent_id,
        "strategy_id": foreign_manifest.strategy_id,
        "management_mandate_id": foreign_manifest.management_mandate_id,
        "position_id": calculate_position_id(
            foreign_manifest.run_id,
            foreign_manifest.account_id,
            foreign_manifest.allocation_id,
            foreign_manifest.agent_id,
            InstrumentId.parse("XNYS:AAPL"),
            proposal_id,
        ),
        "proposal_id": proposal_id,
        "entry_fill_ids": (SimulatedFillId.parse(digest("5")),),
        "exit_fill_ids": (SimulatedFillId.parse(digest("6")),),
        "opened_at": BASE,
        "closed_at": BASE + timedelta(minutes=5),
        "quantity": "1",
        "gross_pnl": "5",
        "total_execution_costs": "1",
        "net_pnl": "4",
    }
    trade = RealizedTradeResult.model_validate(
        {
            "realized_trade_result_id": calculate_realized_trade_result_id(trade_content),
            **trade_content,
        }
    )
    finalization = _finalization(artifact, trade_ids=(trade.realized_trade_result_id,))
    events = order_replay_events(
        (
            artifact.events[0],
            replay_event(
                ReplayPhase.PORTFOLIO_UPDATE,
                trade.closed_at,
                payload_kind=ReplayPayloadKind.REALIZED_TRADE,
                payload_id=trade.realized_trade_result_id,
            ),
            replay_event(
                ReplayPhase.RESULT_FINALIZATION,
                finalization.finalized_at,
                payload_id=finalization.payload_id,
            ),
        )
    )
    with pytest.raises(ValidationError, match="run or ownership"):
        _validate_changed_artifact(
            artifact,
            events=events,
            realized_trades=(trade,),
            finalizations=(finalization,),
        )


def test_replay_artifact_rejects_phase_semantic_substitution() -> None:
    artifact = minimal_replay_artifact(status=SimulationResultStatus.INCOMPLETE)
    event = replay_event(
        ReplayPhase.PORTFOLIO_UPDATE,
        artifact.portfolio_snapshots[0].as_of,
        payload_kind=ReplayPayloadKind.POSITION_CHANGE,
        payload_id=artifact.portfolio_snapshots[0].portfolio_snapshot_id,
    )
    events = order_replay_events((event, artifact.events[-1]))
    with pytest.raises(ValidationError, match="missing or unreferenced"):
        _validate_changed_artifact(artifact, events=events)


def test_future_fill_cannot_be_scheduled_before_its_causal_availability() -> None:
    artifact = minimal_replay_artifact(status=SimulationResultStatus.INCOMPLETE)
    order = simulated_order()
    source = market_event()
    fill = simulated_fill()
    malicious_fill_event = replay_event(
        ReplayPhase.FILL,
        order.eligible_at,
        payload_id=fill.fill_id,
    )
    events = order_replay_events(
        (
            artifact.events[0],
            replay_event(
                ReplayPhase.ORDER_SUBMISSION,
                order.submitted_at,
                payload_id=order.order_id,
            ),
            malicious_fill_event,
            replay_event(
                ReplayPhase.MARKET_DATA_AVAILABLE,
                source.available_at,
                payload_id=source.market_event_id,
            ),
            artifact.events[-1],
        )
    )
    with pytest.raises(ValidationError, match="timestamp differs.*causality"):
        _validate_changed_artifact(
            artifact,
            events=events,
            market_events=(source,),
            orders=(order,),
            fills=(fill,),
        )


def test_complete_artifact_rejects_unreconciled_fill() -> None:
    artifact = minimal_replay_artifact()
    order = simulated_order()
    source = market_event()
    fill = simulated_fill()
    events = order_replay_events(
        (
            artifact.events[0],
            replay_event(
                ReplayPhase.ORDER_SUBMISSION,
                order.submitted_at,
                payload_id=order.order_id,
            ),
            replay_event(ReplayPhase.FILL, fill.fill_at, payload_id=fill.fill_id),
            replay_event(
                ReplayPhase.MARKET_DATA_AVAILABLE,
                source.available_at,
                payload_id=source.market_event_id,
            ),
            artifact.events[-1],
        )
    )
    with pytest.raises(ValidationError, match="reconcile every fill"):
        _validate_changed_artifact(
            artifact,
            events=events,
            market_events=(source,),
            orders=(order,),
            fills=(fill,),
        )


def test_complete_result_rejects_tampered_derived_linkage() -> None:
    result = SimulationResult.create(minimal_replay_artifact())
    for field, value in (
        ("replay_trace_sha256", "0" * 64),
        ("event_ids", tuple(reversed(result.event_ids))),
        ("final_portfolio_snapshot_id", digest("8")),
        ("finalized_at", BASE - timedelta(seconds=1)),
    ):
        content = result.model_dump(mode="python", exclude={"result_id"})
        content[field] = value
        with pytest.raises(ValidationError, match="does not match|finalization predates"):
            SimulationResult.model_validate(
                {"result_id": calculate_simulation_result_id(content), **content}
            )


def test_finalization_cannot_precede_reconciled_portfolio() -> None:
    artifact = minimal_replay_artifact()
    finalized_at = artifact.finalizations[0].finalized_at
    portfolio = initial_portfolio(as_of=finalized_at + timedelta(seconds=1))
    finalization_content: dict[str, object] = {
        "schema_version": "result-finalization-payload-v1",
        "run_id": artifact.manifest.run_id,
        "status": SimulationResultStatus.COMPLETE,
        "final_portfolio_snapshot_id": portfolio.portfolio_snapshot_id,
        "realized_trade_result_ids": (),
        "finalized_at": finalized_at,
    }
    finalization = ResultFinalizationPayload.model_validate(
        {"payload_id": calculate_marker_payload_id(finalization_content), **finalization_content}
    )
    events = order_replay_events(
        (
            replay_event(
                ReplayPhase.RESULT_FINALIZATION,
                finalized_at,
                payload_id=finalization.payload_id,
            ),
            replay_event(
                ReplayPhase.PORTFOLIO_UPDATE,
                portfolio.as_of,
                payload_id=portfolio.portfolio_snapshot_id,
            ),
        )
    )
    with pytest.raises(ValidationError, match="predates reconciled accounting"):
        _validate_changed_artifact(
            artifact,
            events=events,
            portfolio_snapshots=(portfolio,),
            finalizations=(finalization,),
        )


def test_equal_timestamp_order_and_bytes_are_input_order_independent() -> None:
    events = tuple(
        replay_event(
            ReplayPhase.MARKET_DATA_AVAILABLE,
            BASE,
            payload_id=digest(character),
        )
        for character in "13579bdf"
    )
    expected = order_replay_events(events)
    assert order_replay_events(tuple(reversed(events))) == expected
    assert serialize_replay_events(order_replay_events(events[::2] + events[1::2])) == (
        serialize_replay_events(expected)
    )


def test_caller_supplied_tie_break_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        replay_event(tie_break_key="agent:A|AAPL|caller-choice")
