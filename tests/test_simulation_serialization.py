from datetime import timedelta

import pytest
from pydantic import ValidationError
from simulation_helpers import BASE, digest, initial_portfolio, replay_event, run_manifest

from ai_trading_scanner.simulation import (
    ReplayArtifactBundle,
    ReplayEvent,
    ReplayPayloadKind,
    ReplayPhase,
    ResultFinalizationPayload,
    SimulationResult,
    SimulationResultStatus,
    calculate_marker_payload_id,
    calculate_replay_artifact_id,
    calculate_replay_trace_hash,
    calculate_simulation_result_id,
    order_replay_events,
    serialize_replay_events,
    validate_replay_trace,
)


def canonical_trace() -> tuple[ReplayEvent, ...]:
    return (
        replay_event(
            ReplayPhase.FILL,
            BASE,
            payload_kind=ReplayPayloadKind.SIMULATED_FILL,
            payload_id=digest("1"),
        ),
        replay_event(
            ReplayPhase.PORTFOLIO_UPDATE,
            BASE,
            payload_kind=ReplayPayloadKind.PORTFOLIO_SNAPSHOT,
            payload_id=digest("2"),
        ),
        replay_event(
            ReplayPhase.MARKET_DATA_AVAILABLE,
            BASE,
            payload_kind=ReplayPayloadKind.MARKET_EVENT,
            payload_id=digest("3"),
        ),
        replay_event(
            ReplayPhase.STRATEGY_EVALUATION,
            BASE,
            payload_kind=ReplayPayloadKind.STRATEGY_DECISION,
            payload_id=digest("4"),
        ),
        replay_event(
            ReplayPhase.ORDER_SUBMISSION,
            BASE,
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


def test_same_phase_tie_break_is_semantic_and_caller_cannot_override_it() -> None:
    first = replay_event(ReplayPhase.MARKET_DATA_AVAILABLE, BASE, payload_id=digest("7"))
    second = replay_event(
        ReplayPhase.MARKET_DATA_AVAILABLE,
        BASE,
        payload_id=digest("8"),
    )
    assert order_replay_events((second, first)) == order_replay_events((first, second))
    with pytest.raises(ValidationError, match="Extra inputs"):
        replay_event(tie_break_key="caller-controlled")


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


def replay_artifact() -> ReplayArtifactBundle:
    manifest = run_manifest()
    portfolio = initial_portfolio()
    finalization_content: dict[str, object] = {
        "schema_version": "result-finalization-payload-v1",
        "run_id": manifest.run_id,
        "status": SimulationResultStatus.COMPLETE,
        "final_portfolio_snapshot_id": portfolio.portfolio_snapshot_id,
        "realized_trade_result_ids": (),
        "finalized_at": BASE + timedelta(minutes=10),
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
            portfolio.as_of,
            payload_id=portfolio.portfolio_snapshot_id,
        ),
        replay_event(
            ReplayPhase.RESULT_FINALIZATION,
            finalization.finalized_at,
            payload_id=finalization.payload_id,
        ),
    )
    return ReplayArtifactBundle.create(
        manifest=manifest,
        events=events,
        portfolio_snapshots=(portfolio,),
        finalizations=(finalization,),
    )


def simulation_result() -> SimulationResult:
    return SimulationResult.create(replay_artifact())


def test_result_identity_is_stable_and_binds_complete_trace() -> None:
    first = simulation_result()
    second = simulation_result()
    assert first == second

    content = first.model_dump(mode="python")
    content["status"] = SimulationResultStatus.INCOMPLETE
    content["result_id"] = calculate_simulation_result_id(content)
    with pytest.raises(ValidationError, match="does not match"):
        SimulationResult.model_validate(content)


def test_result_rejects_tampered_trace_or_event_linkage() -> None:
    result = simulation_result()
    for field, value in (
        ("replay_trace_sha256", "0" * 64),
        ("event_ids", tuple(reversed(result.event_ids))),
    ):
        content = result.model_dump(mode="python")
        content[field] = value
        content["result_id"] = calculate_simulation_result_id(content)
        with pytest.raises(ValidationError, match="does not match"):
            SimulationResult.model_validate(content)


def test_artifact_identity_rejects_payload_tampering() -> None:
    artifact = replay_artifact()
    content = artifact.model_dump(mode="python")
    content["artifact_id"] = calculate_replay_artifact_id(content)
    content["events"] = tuple(reversed(content["events"]))
    with pytest.raises(ValidationError, match="canonically ordered"):
        ReplayArtifactBundle.model_validate(content)
