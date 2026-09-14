from datetime import timedelta

import pytest
from pydantic import ValidationError
from simulation_helpers import BASE, digest, initial_portfolio, replay_event, run_manifest

from ai_trading_scanner.domain import RealizedTradeResultId
from ai_trading_scanner.simulation import (
    ReplayEvent,
    ReplayPayloadKind,
    ReplayPhase,
    SimulationResult,
    SimulationResultStatus,
    calculate_replay_trace_hash,
    calculate_simulation_result_id,
    serialize_replay_events,
    validate_replay_trace,
)


def canonical_trace() -> tuple[ReplayEvent, ...]:
    return (
        replay_event(
            ReplayPhase.FILL,
            BASE,
            "fill:0001",
            payload_kind=ReplayPayloadKind.SIMULATED_FILL,
            payload_id=digest("1"),
        ),
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            BASE,
            "portfolio:0001",
            payload_kind=ReplayPayloadKind.PORTFOLIO_SNAPSHOT,
            payload_id=digest("2"),
        ),
        replay_event(
            ReplayPhase.MARKET_DATA_AVAILABLE,
            BASE,
            "market:0001",
            payload_kind=ReplayPayloadKind.MARKET_EVENT,
            payload_id=digest("3"),
        ),
        replay_event(
            ReplayPhase.STRATEGY_EVALUATION,
            BASE,
            "decision:0001",
            payload_kind=ReplayPayloadKind.STRATEGY_DECISION,
            payload_id=digest("4"),
        ),
        replay_event(
            ReplayPhase.ORDER_SUBMISSION,
            BASE,
            "order:0001",
            payload_kind=ReplayPayloadKind.SIMULATED_ORDER,
            payload_id=digest("5"),
        ),
    )


def trace() -> tuple[ReplayEvent, ...]:
    return tuple(canonical_trace())


def test_same_timestamp_events_follow_versioned_causal_phase_order() -> None:
    events = trace()
    validate_replay_trace(events)
    assert [event.phase for event in events] == [
        ReplayPhase.FILL,
        ReplayPhase.PORTFOLIO_UPDATE,
        ReplayPhase.MARKET_DATA_AVAILABLE,
        ReplayPhase.STRATEGY_EVALUATION,
        ReplayPhase.ORDER_SUBMISSION,
    ]


def test_out_of_order_duplicate_or_mixed_run_trace_fails_closed() -> None:
    events = trace()
    with pytest.raises(ValueError, match="canonical"):
        validate_replay_trace(tuple(reversed(events)))
    with pytest.raises(ValueError, match="duplicate event"):
        validate_replay_trace((events[0], events[0]))
    other_run = run_manifest(starting_capital="100")
    foreign = replay_event(run_id=other_run.run_id)
    with pytest.raises(ValueError, match="mix run"):
        validate_replay_trace((events[0], foreign))


def test_tie_break_key_is_required_for_same_phase_determinism() -> None:
    first = replay_event(ReplayPhase.MARKET_DATA_AVAILABLE, BASE, "same")
    second = replay_event(
        ReplayPhase.MARKET_DATA_AVAILABLE,
        BASE,
        "same",
        payload_id=digest("8"),
    )
    with pytest.raises(ValueError, match="ordering keys"):
        validate_replay_trace((first, second))


def test_canonical_ndjson_serialization_and_trace_hash_are_stable() -> None:
    events = trace()
    first = serialize_replay_events(events)
    second = serialize_replay_events(events)

    assert first == second
    assert first.endswith(b"\n")
    assert first.count(b"\n") == len(events)
    assert calculate_replay_trace_hash(events) == calculate_replay_trace_hash(events)


def test_event_identity_changes_with_time_phase_or_payload() -> None:
    original = replay_event()
    assert replay_event(scheduled_at=BASE + timedelta(seconds=1)).replay_event_id != (
        original.replay_event_id
    )
    assert (
        replay_event(phase=ReplayPhase.RISK_EVALUATION).replay_event_id != original.replay_event_id
    )
    assert replay_event(payload_id=digest("7")).replay_event_id != original.replay_event_id


def test_replay_event_rejects_payload_kind_incompatible_with_phase() -> None:
    with pytest.raises(ValidationError, match="incompatible"):
        replay_event(
            phase=ReplayPhase.FILL,
            payload_kind=ReplayPayloadKind.STRATEGY_DECISION,
        )


def test_replay_event_rejects_naive_timestamp_and_stale_identity() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        replay_event(scheduled_at=BASE.replace(tzinfo=None))

    event = replay_event()
    content = event.model_dump(mode="python")
    content["scheduled_at"] = BASE + timedelta(seconds=1)
    with pytest.raises(ValidationError, match="identity"):
        type(event).model_validate(content)


def simulation_result(**changes: object) -> SimulationResult:
    events = trace()
    content: dict[str, object] = {
        "schema_version": "simulation-result-v1",
        "run_id": run_manifest().run_id,
        "status": SimulationResultStatus.COMPLETE,
        "replay_trace_sha256": calculate_replay_trace_hash(events),
        "event_ids": tuple(event.replay_event_id for event in events),
        "final_portfolio_snapshot_id": initial_portfolio().portfolio_snapshot_id,
        "realized_trade_result_ids": (RealizedTradeResultId.parse(digest("6")),),
        "finalized_at": BASE + timedelta(minutes=10),
    }
    content.update(changes)
    return SimulationResult.model_validate(
        {"result_id": calculate_simulation_result_id(content), **content}
    )


def test_result_identity_is_stable_and_binds_complete_trace() -> None:
    first = simulation_result()
    second = simulation_result()
    assert first == second

    changed = simulation_result(status=SimulationResultStatus.INCOMPLETE)
    assert changed.result_id != first.result_id


def test_result_rejects_duplicate_event_or_trade_linkage() -> None:
    result = simulation_result()
    with pytest.raises(ValidationError, match="event identities"):
        simulation_result(event_ids=(result.event_ids[0], result.event_ids[0]))
    duplicate_trade = result.realized_trade_result_ids[0]
    with pytest.raises(ValidationError, match="realized trade"):
        simulation_result(realized_trade_result_ids=(duplicate_trade, duplicate_trade))
