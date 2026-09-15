from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import cast

import pytest
from pydantic import ValidationError
from simulation_helpers import BASE, digest, replay_event, run_manifest
from test_simulation_remediation_3 import _artifact_content, _two_instrument_same_time_artifact

from ai_trading_scanner.simulation import (
    DeterministicReplayScheduler,
    ReplayArtifactBundle,
    ReplayEvent,
    ReplayPayloadKind,
    ReplayPhase,
    ReplaySchedule,
    ReplaySchedulerCheckpoint,
    SchedulerCheckpointError,
    SchedulerExhaustedError,
    calculate_replay_event_id,
    calculate_replay_schedule_id,
    calculate_replay_scheduler_checkpoint_id,
)


def _event(
    phase: ReplayPhase,
    *,
    seconds: int = 0,
    identity_char: str,
    run_id: object | None = None,
    payload_kind: ReplayPayloadKind | None = None,
) -> ReplayEvent:
    changes: dict[str, object] = {"payload_id": digest(identity_char)}
    if run_id is not None:
        changes["run_id"] = run_id
    if payload_kind is not None:
        changes["payload_kind"] = payload_kind
    return replay_event(phase, BASE + timedelta(seconds=seconds), **changes)


def _events() -> tuple[ReplayEvent, ...]:
    return (
        _event(ReplayPhase.MARKET_DATA_AVAILABLE, seconds=5, identity_char="5"),
        _event(ReplayPhase.FILL, seconds=2, identity_char="2"),
        _event(ReplayPhase.PORTFOLIO_UPDATE, seconds=2, identity_char="3"),
        _event(ReplayPhase.EXECUTION_RESOLUTION, seconds=2, identity_char="1"),
        _event(ReplayPhase.INDICATOR_UPDATE, seconds=5, identity_char="6"),
        _event(ReplayPhase.RESULT_FINALIZATION, seconds=9, identity_char="9"),
    )


def _consume(scheduler: DeterministicReplayScheduler) -> tuple[ReplayEvent, ...]:
    consumed: list[ReplayEvent] = []
    while scheduler.has_events:
        consumed.append(scheduler.next_event())
    return tuple(consumed)


def test_scheduler_orders_increasing_timestamps() -> None:
    scheduler = DeterministicReplayScheduler.from_events(reversed(_events()))
    timestamps = tuple(event.scheduled_at for event in scheduler.schedule.events)
    assert timestamps == tuple(sorted(timestamps))


def test_scheduler_uses_authoritative_phase_precedence_at_identical_time() -> None:
    scheduler = DeterministicReplayScheduler.from_events(_events())
    phases = tuple(
        event.phase
        for event in scheduler.schedule.events
        if event.scheduled_at == BASE + timedelta(seconds=2)
    )
    assert phases == (
        ReplayPhase.EXECUTION_RESOLUTION,
        ReplayPhase.FILL,
        ReplayPhase.PORTFOLIO_UPDATE,
    )


def test_same_phase_same_time_uses_semantic_payload_tie_break() -> None:
    events = tuple(
        _event(ReplayPhase.MARKET_DATA_AVAILABLE, identity_char=char) for char in ("c", "a", "b")
    )
    scheduler = DeterministicReplayScheduler.from_events(events)
    assert tuple(event.payload_id for event in scheduler.schedule.events) == tuple(
        sorted(event.payload_id for event in events)
    )


def test_multiple_instruments_at_identical_time_remain_deterministic() -> None:
    artifact = _two_instrument_same_time_artifact()
    scheduler = DeterministicReplayScheduler.from_artifact(artifact)
    at = artifact.fills[0].fill_at
    market_ids = tuple(
        event.payload_id
        for event in scheduler.schedule.events
        if event.scheduled_at == at and event.payload_kind is ReplayPayloadKind.MARKET_EVENT
    )
    assert market_ids == tuple(sorted(market_ids))
    assert len(market_ids) == 2


def test_shuffled_input_produces_identical_schedule_and_identity() -> None:
    events = _events()
    expected = ReplaySchedule.create(events)
    for seed in range(25):
        shuffled = list(events)
        random.Random(seed).shuffle(shuffled)
        actual = ReplaySchedule.create(shuffled)
        assert actual == expected
        assert actual.schedule_id == expected.schedule_id
        assert actual.model_dump_json() == expected.model_dump_json()


def test_repeated_and_json_reconstructed_schedule_is_identical() -> None:
    first = ReplaySchedule.create(_events())
    second = ReplaySchedule.create(_events())
    reconstructed = ReplaySchedule.model_validate_json(first.model_dump_json())
    assert first == second == reconstructed
    assert first.schedule_id == second.schedule_id == reconstructed.schedule_id


def test_every_event_is_consumed_exactly_once() -> None:
    scheduler = DeterministicReplayScheduler.from_events(_events())
    consumed = _consume(scheduler)
    assert consumed == scheduler.schedule.events
    assert len({event.replay_event_id for event in consumed}) == len(consumed)
    assert scheduler.position == len(consumed)


def test_concurrent_consumers_cannot_consume_an_event_twice() -> None:
    events = tuple(
        replay_event(
            ReplayPhase.MARKET_DATA_AVAILABLE,
            BASE + timedelta(seconds=index),
            payload_id=f"market-event:{index}",
        )
        for index in range(64)
    )
    scheduler = DeterministicReplayScheduler.from_events(reversed(events))

    def consume_one(_: int) -> ReplayEvent | None:
        try:
            return scheduler.next_event()
        except SchedulerExhaustedError:
            return None

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = tuple(pool.map(consume_one, range(96)))
    consumed = tuple(event for event in results if event is not None)
    assert len(consumed) == len(events)
    assert len({event.replay_event_id for event in consumed}) == len(events)
    assert scheduler.exhausted
    assert scheduler.position == len(events)


def test_exhaustion_state_is_deterministic() -> None:
    scheduler = DeterministicReplayScheduler.from_events(_events())
    _consume(scheduler)
    before = scheduler.state
    assert scheduler.exhausted
    assert not scheduler.has_events
    assert scheduler.remaining == 0
    with pytest.raises(SchedulerExhaustedError, match="exhausted"):
        scheduler.peek_next()
    assert scheduler.state == before


def test_consume_after_exhaustion_fails_closed_without_advancing() -> None:
    scheduler = DeterministicReplayScheduler.from_events(_events())
    _consume(scheduler)
    position = scheduler.position
    with pytest.raises(SchedulerExhaustedError, match="exhausted"):
        scheduler.next_event()
    assert scheduler.position == position


def test_duplicate_event_ids_are_rejected() -> None:
    event = _events()[0]
    with pytest.raises(ValueError, match="duplicate event identities"):
        ReplaySchedule.create((event, event))


def test_conflicting_reused_event_id_is_revalidated_and_rejected() -> None:
    original = _events()[0]
    forged = original.model_copy(update={"payload_id": digest("8")})
    with pytest.raises(ValidationError, match="identity does not match"):
        ReplaySchedule.create((original, forged))


def test_cross_run_event_contamination_is_rejected() -> None:
    other = run_manifest(starting_capital="51")
    foreign = _event(
        ReplayPhase.MARKET_DATA_AVAILABLE,
        seconds=7,
        identity_char="7",
        run_id=other.run_id,
    )
    with pytest.raises(ValueError, match="mix run identities"):
        ReplaySchedule.create((*_events(), foreign))


@pytest.mark.parametrize("corruption", ["stale-payload", "incompatible-phase"])
def test_invalid_payload_event_linkage_is_rejected(corruption: str) -> None:
    event = _events()[0]
    content = event.model_dump(mode="python")
    if corruption == "stale-payload":
        content["payload_id"] = digest("8")
    else:
        content["payload_kind"] = ReplayPayloadKind.SIMULATED_FILL
        content["replay_event_id"] = calculate_replay_event_id(content)
    with pytest.raises(ValidationError):
        ReplaySchedule.create((content,))


def test_checkpoint_resume_produces_identical_continuation() -> None:
    original = DeterministicReplayScheduler.from_events(_events())
    original.next_event()
    original.next_event()
    checkpoint = original.checkpoint()
    expected = _consume(original)

    reconstructed_schedule = ReplaySchedule.model_validate_json(original.schedule.model_dump_json())
    reconstructed_checkpoint = ReplaySchedulerCheckpoint.model_validate_json(
        checkpoint.model_dump_json()
    )
    resumed = DeterministicReplayScheduler(reconstructed_schedule, reconstructed_checkpoint)
    assert _consume(resumed) == expected


def test_checkpoint_from_another_schedule_is_rejected() -> None:
    first = DeterministicReplayScheduler.from_events(_events())
    first.next_event()
    checkpoint = first.checkpoint()
    changed = (
        *_events()[:-1],
        _event(ReplayPhase.RESULT_FINALIZATION, seconds=10, identity_char="8"),
    )
    other = ReplaySchedule.create(changed)
    with pytest.raises(SchedulerCheckpointError, match="another schedule"):
        DeterministicReplayScheduler(other, checkpoint)


def test_market_data_availability_retains_causal_position() -> None:
    artifact = _two_instrument_same_time_artifact()
    scheduler = DeterministicReplayScheduler.from_artifact(artifact)
    at = artifact.fills[0].fill_at
    kinds = tuple(
        event.payload_kind for event in scheduler.schedule.events if event.scheduled_at == at
    )
    for prerequisite in (
        ReplayPayloadKind.EXECUTION_RESOLUTION,
        ReplayPayloadKind.SIMULATED_FILL,
        ReplayPayloadKind.POSITION_CHANGE,
        ReplayPayloadKind.PORTFOLIO_SNAPSHOT,
    ):
        assert kinds.index(prerequisite) < kinds.index(ReplayPayloadKind.MARKET_EVENT)


def test_equal_time_accounting_chain_preserves_accepted_precedence() -> None:
    artifact = _two_instrument_same_time_artifact()
    events = DeterministicReplayScheduler.from_artifact(artifact).schedule.events
    at = artifact.fills[0].fill_at
    kinds = tuple(event.payload_kind for event in events if event.scheduled_at == at)
    assert kinds.index(ReplayPayloadKind.SIMULATED_FILL) < kinds.index(
        ReplayPayloadKind.POSITION_CHANGE
    )
    assert kinds.index(ReplayPayloadKind.POSITION_CHANGE) < kinds.index(
        ReplayPayloadKind.PORTFOLIO_SNAPSHOT
    )


def test_semantically_different_schedule_has_different_identity() -> None:
    original = ReplaySchedule.create(_events())
    changed = ReplaySchedule.create(
        (*_events()[:-1], _event(ReplayPhase.RESULT_FINALIZATION, seconds=10, identity_char="8"))
    )
    assert original.schedule_id != changed.schedule_id
    assert original.replay_trace_sha256 != changed.replay_trace_sha256


def test_caller_mutation_cannot_change_constructed_schedule() -> None:
    supplied = list(_events())
    scheduler = DeterministicReplayScheduler.from_events(supplied)
    before = scheduler.schedule.model_dump_json()
    supplied.clear()
    assert scheduler.schedule.model_dump_json() == before
    assert scheduler.remaining == len(_events())


def test_checkpoint_with_skipped_or_forged_prefix_is_rejected() -> None:
    scheduler = DeterministicReplayScheduler.from_events(_events())
    scheduler.next_event()
    checkpoint = scheduler.checkpoint()
    content = checkpoint.model_dump(mode="python", exclude={"checkpoint_id"})
    content["consumed_event_ids"] = (scheduler.schedule.events[1].replay_event_id,)
    forged = ReplaySchedulerCheckpoint.model_validate(
        {
            "checkpoint_id": calculate_replay_scheduler_checkpoint_id(content),
            **content,
        }
    )
    with pytest.raises(SchedulerCheckpointError, match="another schedule"):
        DeterministicReplayScheduler(scheduler.schedule, forged)


def test_out_of_range_or_ambiguous_checkpoint_is_rejected() -> None:
    schedule = ReplaySchedule.create(_events())
    with pytest.raises(ValueError, match="outside the schedule"):
        ReplaySchedulerCheckpoint.create(schedule, len(schedule.events) + 1)

    checkpoint = ReplaySchedulerCheckpoint.create(schedule, 1)
    content = checkpoint.model_dump(mode="python", exclude={"checkpoint_id"})
    content["next_event_id"] = None
    with pytest.raises(ValidationError, match="next event is inconsistent"):
        ReplaySchedulerCheckpoint.model_validate(
            {
                "checkpoint_id": calculate_replay_scheduler_checkpoint_id(content),
                **content,
            }
        )


def test_exhausted_checkpoint_resumes_exhausted() -> None:
    scheduler = DeterministicReplayScheduler.from_events(_events())
    _consume(scheduler)
    resumed = DeterministicReplayScheduler(scheduler.schedule, scheduler.checkpoint())
    assert resumed.exhausted
    with pytest.raises(SchedulerExhaustedError):
        resumed.next_event()


def test_peek_does_not_consume_or_change_state() -> None:
    scheduler = DeterministicReplayScheduler.from_events(_events())
    before = scheduler.state
    assert scheduler.peek_next() == scheduler.schedule.events[0]
    assert scheduler.state == before


def test_caller_cannot_set_or_skip_scheduler_position() -> None:
    scheduler = DeterministicReplayScheduler.from_events(_events())
    with pytest.raises(AttributeError):
        scheduler.position = 3  # type: ignore[misc]
    assert scheduler.position == 0


def test_direct_noncanonical_schedule_load_fails_closed() -> None:
    schedule = ReplaySchedule.create(_events())
    content = schedule.model_dump(mode="python", exclude={"schedule_id"})
    content["events"] = tuple(reversed(cast(tuple[ReplayEvent, ...], content["events"])))
    with pytest.raises(ValidationError, match="canonical event order"):
        ReplaySchedule.model_validate(
            {"schedule_id": calculate_replay_schedule_id(content), **content}
        )


def test_artifact_registry_order_does_not_change_schedule() -> None:
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
    assert ReplaySchedule.from_artifact(rebuilt) == ReplaySchedule.from_artifact(artifact)


def test_from_artifact_revalidates_typed_payload_linkage() -> None:
    artifact = _two_instrument_same_time_artifact()
    forged_market = artifact.market_events[0].model_copy(
        update={"source_record_id": "tampered-after-validation"}
    )
    forged = artifact.model_copy(
        update={"market_events": (forged_market, *artifact.market_events[1:])}
    )
    with pytest.raises(ValidationError, match="market event identity does not match"):
        DeterministicReplayScheduler.from_artifact(forged)
