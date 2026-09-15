from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import cast

import pytest
from pydantic import ValidationError
from simulation_helpers import BASE, minimal_replay_artifact, replay_event, run_manifest
from test_simulation_remediation_3 import _artifact_content, _two_instrument_same_time_artifact

import ai_trading_scanner.simulation.scheduler as scheduler_module
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
    SimulationResultStatus,
    calculate_marker_payload_id,
    calculate_replay_event_id,
    calculate_replay_schedule_id,
    calculate_replay_scheduler_checkpoint_id,
    calculate_replay_trace_hash,
    order_replay_events,
)


@pytest.fixture(autouse=True)
def _isolated_process_cursor_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test receives a new process-local scheduler trust boundary."""
    monkeypatch.setattr(scheduler_module, "_PROCESS_CURSOR_STATES", {})


def _artifact() -> ReplayArtifactBundle:
    return _two_instrument_same_time_artifact()


def _consume(scheduler: DeterministicReplayScheduler) -> tuple[ReplayEvent, ...]:
    consumed: list[ReplayEvent] = []
    while scheduler.has_events:
        consumed.append(scheduler.next_event())
    return tuple(consumed)


def _reidentified_event(event: ReplayEvent, **changes: object) -> ReplayEvent:
    content = event.model_dump(mode="python", exclude={"replay_event_id"})
    content.update(changes)
    return ReplayEvent.model_validate(
        {"replay_event_id": calculate_replay_event_id(content), **content}
    )


def _shuffled_artifact(seed: int) -> ReplayArtifactBundle:
    artifact = _artifact()
    content = _artifact_content(artifact)
    randomizer = random.Random(seed)
    for field in (
        "events",
        "execution_resolutions",
        "market_events",
        "orders",
        "fills",
        "position_changes",
        "portfolio_snapshots",
    ):
        values = list(cast(tuple[object, ...], content[field]))
        randomizer.shuffle(values)
        content[field] = tuple(values)
    return ReplayArtifactBundle.create(**content)


def _checkpoint_content(schedule: ReplaySchedule, next_position: int) -> dict[str, object]:
    return {
        "schema_version": "replay-scheduler-checkpoint-v1",
        "schedule_id": schedule.schedule_id,
        "run_id": schedule.run_id,
        "next_position": next_position,
        "total_events": len(schedule.events),
        "consumed_event_ids": tuple(
            event.replay_event_id for event in schedule.events[:next_position]
        ),
        "next_event_id": (
            schedule.events[next_position].replay_event_id
            if next_position < len(schedule.events)
            else None
        ),
    }


def _forged_checkpoint(
    schedule: ReplaySchedule, next_position: int, **changes: object
) -> ReplaySchedulerCheckpoint:
    content = _checkpoint_content(schedule, next_position)
    content.update(changes)
    return ReplaySchedulerCheckpoint.model_validate(
        {"checkpoint_id": calculate_replay_scheduler_checkpoint_id(content), **content}
    )


def test_schedule_exactly_reuses_authoritative_event_order() -> None:
    artifact = _artifact()
    schedule = ReplaySchedule.from_artifact(artifact)
    assert schedule.events == order_replay_events(artifact.events)


def test_scheduler_orders_increasing_timestamps() -> None:
    scheduler = DeterministicReplayScheduler.from_artifact(_artifact())
    timestamps = tuple(event.scheduled_at for event in scheduler.schedule.events)
    assert timestamps == tuple(sorted(timestamps))


def test_scheduler_uses_authoritative_phase_precedence_at_identical_time() -> None:
    artifact = _artifact()
    scheduler = DeterministicReplayScheduler.from_artifact(artifact)
    fill_at = artifact.fills[0].fill_at
    phases = tuple(
        event.phase for event in scheduler.schedule.events if event.scheduled_at == fill_at
    )
    assert phases == tuple(sorted(phases))


def test_same_phase_same_time_uses_semantic_payload_tie_break() -> None:
    artifact = _artifact()
    scheduler = DeterministicReplayScheduler.from_artifact(artifact)
    at = artifact.fills[0].fill_at
    market_ids = tuple(
        event.payload_id
        for event in scheduler.schedule.events
        if event.scheduled_at == at and event.payload_kind is ReplayPayloadKind.MARKET_EVENT
    )
    assert market_ids == tuple(sorted(market_ids))
    assert len(market_ids) == 2


def test_shuffled_valid_artifact_produces_identical_schedule_and_identity() -> None:
    expected = ReplaySchedule.from_artifact(_artifact())
    for seed in range(25):
        actual = ReplaySchedule.from_artifact(_shuffled_artifact(seed))
        assert actual == expected
        assert actual.schedule_id == expected.schedule_id
        assert actual.model_dump_json() == expected.model_dump_json()


def test_repeated_and_json_reconstructed_schedule_is_identical() -> None:
    first = ReplaySchedule.from_artifact(_artifact())
    second = ReplaySchedule.from_artifact(_artifact())
    reconstructed = ReplaySchedule.model_validate_json(first.model_dump_json())
    assert first == second == reconstructed


def test_executable_scheduler_requires_typed_artifact() -> None:
    schedule = ReplaySchedule.from_artifact(_artifact())
    with pytest.raises(TypeError, match="requires ReplayArtifactBundle"):
        DeterministicReplayScheduler(cast(ReplayArtifactBundle, schedule))


def test_raw_event_constructor_is_not_public() -> None:
    assert not hasattr(ReplaySchedule, "create")
    assert not hasattr(DeterministicReplayScheduler, "from_events")


def test_unresolved_raw_event_cannot_create_executable_scheduler() -> None:
    unresolved = replay_event(
        ReplayPhase.MARKET_DATA_AVAILABLE,
        BASE + timedelta(seconds=20),
        payload_id="market-event:not-in-a-typed-registry",
    )
    content: dict[str, object] = {
        "schema_version": "replay-schedule-v1",
        "run_id": unresolved.run_id,
        "replay_trace_sha256": calculate_replay_trace_hash((unresolved,)),
        "events": (unresolved,),
    }
    raw_schedule = ReplaySchedule.model_validate(
        {"schedule_id": calculate_replay_schedule_id(content), **content}
    )
    with pytest.raises(TypeError, match="requires ReplayArtifactBundle"):
        DeterministicReplayScheduler(cast(ReplayArtifactBundle, raw_schedule))


def test_duplicate_payload_reference_fails_authoritative_artifact_validation() -> None:
    artifact = _artifact()
    market = next(
        event for event in artifact.events if event.payload_kind is ReplayPayloadKind.MARKET_EVENT
    )
    duplicate = _reidentified_event(
        market, scheduled_at=market.scheduled_at + timedelta(microseconds=1)
    )
    content = _artifact_content(artifact)
    content["events"] = order_replay_events((*artifact.events, duplicate))
    with pytest.raises(ValidationError, match="references one payload more than once"):
        ReplayArtifactBundle.create(**content)


def test_missing_typed_registry_payload_fails_authoritative_validation() -> None:
    artifact = _artifact()
    forged = artifact.model_copy(update={"market_events": artifact.market_events[1:]})
    with pytest.raises(ValidationError):
        DeterministicReplayScheduler.from_artifact(forged)


def test_event_payload_timestamp_mismatch_fails_authoritative_validation() -> None:
    artifact = _artifact()
    market = next(
        event for event in artifact.events if event.payload_kind is ReplayPayloadKind.MARKET_EVENT
    )
    changed = _reidentified_event(
        market, scheduled_at=market.scheduled_at + timedelta(microseconds=1)
    )
    forged_events = order_replay_events(
        tuple(changed if event == market else event for event in artifact.events)
    )
    content = _artifact_content(artifact)
    content["events"] = forged_events
    with pytest.raises(ValidationError, match="timestamp differs from typed payload causality"):
        ReplayArtifactBundle.create(**content)


def test_foreign_run_payload_fails_authoritative_validation() -> None:
    artifact = _artifact()
    foreign_run = run_manifest(starting_capital="51").run_id
    content = artifact.finalizations[0].model_dump(mode="python", exclude={"payload_id"})
    content["run_id"] = foreign_run
    finalization = type(artifact.finalizations[0]).model_validate(
        {"payload_id": calculate_marker_payload_id(content), **content}
    )
    forged = artifact.model_copy(update={"finalizations": (finalization,)})
    with pytest.raises(ValidationError, match="finalization belongs to a foreign run"):
        DeterministicReplayScheduler.from_artifact(forged)


def test_manifest_run_mismatch_fails_authoritative_validation() -> None:
    artifact = _artifact()
    forged = artifact.model_copy(update={"manifest": run_manifest(starting_capital="51")})
    with pytest.raises(ValidationError):
        DeterministicReplayScheduler.from_artifact(forged)


def test_fully_valid_artifact_creates_executable_scheduler() -> None:
    artifact = _artifact()
    scheduler = DeterministicReplayScheduler.from_artifact(artifact)
    assert scheduler.run_id == artifact.manifest.run_id
    assert scheduler.schedule.events == artifact.events


def test_every_event_is_consumed_exactly_once() -> None:
    scheduler = DeterministicReplayScheduler.from_artifact(_artifact())
    consumed = _consume(scheduler)
    assert consumed == scheduler.schedule.events
    assert len({event.replay_event_id for event in consumed}) == len(consumed)


def test_concurrent_consumers_cannot_consume_an_event_twice() -> None:
    scheduler = DeterministicReplayScheduler.from_artifact(_artifact())

    def consume_one(_: int) -> ReplayEvent | None:
        try:
            return scheduler.next_event()
        except SchedulerExhaustedError:
            return None

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = tuple(pool.map(consume_one, range(len(scheduler.schedule.events) + 32)))
    consumed = tuple(event for event in results if event is not None)
    assert len(consumed) == len(scheduler.schedule.events)
    assert len({event.replay_event_id for event in consumed}) == len(consumed)
    assert scheduler.exhausted


def test_duplicate_scheduler_handles_share_one_process_cursor() -> None:
    first = DeterministicReplayScheduler.from_artifact(_artifact())
    second = DeterministicReplayScheduler.from_artifact(_artifact())
    assert first.next_event() == first.schedule.events[0]
    assert second.position == 1
    assert second.next_event() == first.schedule.events[1]
    assert first.position == 2


def test_new_handle_cannot_replay_an_exhausted_process_cursor() -> None:
    artifact = _artifact()
    first = DeterministicReplayScheduler.from_artifact(artifact)
    _consume(first)
    second = DeterministicReplayScheduler.from_artifact(artifact)
    assert second.exhausted
    with pytest.raises(SchedulerExhaustedError):
        second.next_event()


def test_concurrent_consumers_across_handles_share_exactly_once_progress() -> None:
    artifact = _artifact()
    first = DeterministicReplayScheduler.from_artifact(artifact)
    second = DeterministicReplayScheduler.from_artifact(artifact)

    def consume(index: int) -> ReplayEvent | None:
        scheduler = first if index % 2 == 0 else second
        try:
            return scheduler.next_event()
        except SchedulerExhaustedError:
            return None

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = tuple(pool.map(consume, range(len(first.schedule.events) + 32)))
    consumed = tuple(event for event in results if event is not None)
    assert len(consumed) == len(first.schedule.events)
    assert len({event.replay_event_id for event in consumed}) == len(consumed)
    assert first.exhausted and second.exhausted


def test_exhaustion_state_is_deterministic() -> None:
    scheduler = DeterministicReplayScheduler.from_artifact(_artifact())
    _consume(scheduler)
    before = scheduler.state
    assert scheduler.exhausted
    assert not scheduler.has_events
    assert scheduler.remaining == 0
    with pytest.raises(SchedulerExhaustedError, match="exhausted"):
        scheduler.peek_next()
    assert scheduler.state == before


def test_consume_after_exhaustion_fails_closed_without_advancing() -> None:
    scheduler = DeterministicReplayScheduler.from_artifact(_artifact())
    _consume(scheduler)
    position = scheduler.position
    with pytest.raises(SchedulerExhaustedError, match="exhausted"):
        scheduler.next_event()
    assert scheduler.position == position


def test_cursor_first_middle_final_and_exhausted_states() -> None:
    scheduler = DeterministicReplayScheduler.from_artifact(_artifact())
    assert scheduler.position == 0
    assert scheduler.peek_next() == scheduler.schedule.events[0]
    scheduler.next_event()
    assert scheduler.position == 1
    while scheduler.remaining > 1:
        scheduler.next_event()
    assert scheduler.peek_next() == scheduler.schedule.events[-1]
    scheduler.next_event()
    assert scheduler.exhausted


def test_scheduler_issued_checkpoint_resumes_identical_continuation() -> None:
    artifact = _artifact()
    scheduler = DeterministicReplayScheduler.from_artifact(artifact)
    scheduler.next_event()
    scheduler.next_event()
    checkpoint = scheduler.checkpoint()
    expected = scheduler.schedule.events[checkpoint.next_position :]
    resumed = DeterministicReplayScheduler.from_artifact(artifact, checkpoint=checkpoint)
    assert _consume(resumed) == expected


def test_json_reconstructed_issued_checkpoint_remains_trusted_in_process() -> None:
    artifact = _artifact()
    scheduler = DeterministicReplayScheduler.from_artifact(artifact)
    scheduler.next_event()
    checkpoint = scheduler.checkpoint()
    reconstructed = ReplaySchedulerCheckpoint.model_validate_json(checkpoint.model_dump_json())
    resumed = DeterministicReplayScheduler.from_artifact(artifact, checkpoint=reconstructed)
    assert resumed.position == checkpoint.next_position


@pytest.mark.parametrize("position", [3, -1])
def test_arbitrary_checkpoint_position_cannot_be_publicly_minted(position: int) -> None:
    schedule = ReplaySchedule.from_artifact(_artifact())
    assert not hasattr(ReplaySchedulerCheckpoint, "create")
    if position < 0:
        with pytest.raises(ValidationError):
            _forged_checkpoint(schedule, position)
        return
    forged = _forged_checkpoint(schedule, position)
    with pytest.raises(SchedulerCheckpointError, match="not issued"):
        DeterministicReplayScheduler.from_artifact(_artifact(), checkpoint=forged)


def test_arbitrary_final_checkpoint_is_rejected() -> None:
    artifact = _artifact()
    schedule = ReplaySchedule.from_artifact(artifact)
    forged = _forged_checkpoint(schedule, len(schedule.events))
    with pytest.raises(SchedulerCheckpointError, match="not issued"):
        DeterministicReplayScheduler.from_artifact(artifact, checkpoint=forged)


def test_manufactured_position_zero_after_consumption_is_rejected() -> None:
    artifact = _artifact()
    scheduler = DeterministicReplayScheduler.from_artifact(artifact)
    scheduler.next_event()
    forged = _forged_checkpoint(scheduler.schedule, 0)
    with pytest.raises(SchedulerCheckpointError, match="not issued"):
        DeterministicReplayScheduler.from_artifact(artifact, checkpoint=forged)


def test_recomputed_identity_cannot_elevate_forged_position() -> None:
    artifact = _artifact()
    scheduler = DeterministicReplayScheduler.from_artifact(artifact)
    issued = scheduler.checkpoint()
    forged = _forged_checkpoint(scheduler.schedule, 3)
    assert forged.checkpoint_id != issued.checkpoint_id
    with pytest.raises(SchedulerCheckpointError, match="not issued"):
        DeterministicReplayScheduler.from_artifact(artifact, checkpoint=forged)


@pytest.mark.parametrize("corruption", ["changed-prefix", "reordered-prefix", "wrong-next"])
def test_forged_checkpoint_relationships_are_rejected(corruption: str) -> None:
    artifact = _artifact()
    scheduler = DeterministicReplayScheduler.from_artifact(artifact)
    scheduler.next_event()
    scheduler.next_event()
    checkpoint = scheduler.checkpoint()
    changes: dict[str, object]
    if corruption == "changed-prefix":
        changes = {
            "consumed_event_ids": (
                scheduler.schedule.events[1].replay_event_id,
                scheduler.schedule.events[2].replay_event_id,
            )
        }
    elif corruption == "reordered-prefix":
        changes = {"consumed_event_ids": tuple(reversed(checkpoint.consumed_event_ids))}
    else:
        changes = {"next_event_id": scheduler.schedule.events[3].replay_event_id}
    forged = _forged_checkpoint(scheduler.schedule, checkpoint.next_position, **changes)
    with pytest.raises(SchedulerCheckpointError):
        DeterministicReplayScheduler.from_artifact(artifact, checkpoint=forged)


@pytest.mark.parametrize("corruption", ["schedule", "run", "length"])
def test_wrong_checkpoint_scope_is_rejected(corruption: str) -> None:
    artifact = _artifact()
    scheduler = DeterministicReplayScheduler.from_artifact(artifact)
    scheduler.checkpoint()
    other_schedule = ReplaySchedule.from_artifact(
        minimal_replay_artifact(status=SimulationResultStatus.INCOMPLETE)
    )
    changes: dict[str, object]
    if corruption == "schedule":
        changes = {"schedule_id": other_schedule.schedule_id}
    elif corruption == "run":
        changes = {"run_id": run_manifest(starting_capital="51").run_id}
    else:
        changes = {"total_events": len(scheduler.schedule.events) + 1}
    forged = _forged_checkpoint(scheduler.schedule, 0, **changes)
    with pytest.raises(SchedulerCheckpointError):
        DeterministicReplayScheduler.from_artifact(artifact, checkpoint=forged)


def test_checkpoint_from_another_schedule_is_rejected() -> None:
    first = DeterministicReplayScheduler.from_artifact(_artifact())
    checkpoint = first.checkpoint()
    other = minimal_replay_artifact(status=SimulationResultStatus.INCOMPLETE)
    with pytest.raises(SchedulerCheckpointError):
        DeterministicReplayScheduler.from_artifact(other, checkpoint=checkpoint)


def test_stale_checkpoint_cannot_rewind_progressed_in_memory_cursor() -> None:
    artifact = _artifact()
    scheduler = DeterministicReplayScheduler.from_artifact(artifact)
    scheduler.next_event()
    stale = scheduler.checkpoint()
    scheduler.next_event()
    with pytest.raises(SchedulerCheckpointError, match="not issued"):
        DeterministicReplayScheduler.from_artifact(artifact, checkpoint=stale)
    assert scheduler.position == 2


def test_equivalent_shuffled_artifact_accepts_current_checkpoint() -> None:
    artifact = _artifact()
    scheduler = DeterministicReplayScheduler.from_artifact(artifact)
    scheduler.next_event()
    checkpoint = scheduler.checkpoint()
    equivalent = _shuffled_artifact(91)
    resumed = DeterministicReplayScheduler.from_artifact(equivalent, checkpoint=checkpoint)
    assert resumed.schedule == scheduler.schedule
    assert resumed.position == checkpoint.next_position


def test_checkpoint_exactly_describes_observed_scheduler_state() -> None:
    scheduler = DeterministicReplayScheduler.from_artifact(_artifact())
    for expected_position in range(len(scheduler.schedule.events) + 1):
        checkpoint = scheduler.checkpoint()
        assert checkpoint.next_position == expected_position == scheduler.position
        assert checkpoint.consumed_event_ids == tuple(
            event.replay_event_id for event in scheduler.schedule.events[:expected_position]
        )
        if expected_position < len(scheduler.schedule.events):
            assert (
                checkpoint.next_event_id
                == scheduler.schedule.events[expected_position].replay_event_id
            )
            scheduler.next_event()
        else:
            assert checkpoint.next_event_id is None


def test_peek_does_not_consume_or_change_position() -> None:
    scheduler = DeterministicReplayScheduler.from_artifact(_artifact())
    before = scheduler.position
    assert scheduler.peek_next() == scheduler.schedule.events[0]
    assert scheduler.position == before


def test_caller_cannot_set_or_skip_scheduler_position() -> None:
    scheduler = DeterministicReplayScheduler.from_artifact(_artifact())
    with pytest.raises(AttributeError):
        scheduler.position = 3  # type: ignore[misc]
    assert scheduler.position == 0


def test_market_data_availability_retains_causal_position() -> None:
    artifact = _artifact()
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
    artifact = _artifact()
    events = DeterministicReplayScheduler.from_artifact(artifact).schedule.events
    at = artifact.fills[0].fill_at
    kinds = tuple(event.payload_kind for event in events if event.scheduled_at == at)
    assert kinds.index(ReplayPayloadKind.SIMULATED_FILL) < kinds.index(
        ReplayPayloadKind.POSITION_CHANGE
    )
    assert kinds.index(ReplayPayloadKind.POSITION_CHANGE) < kinds.index(
        ReplayPayloadKind.PORTFOLIO_SNAPSHOT
    )


def test_semantically_different_valid_artifact_has_different_schedule_identity() -> None:
    original = ReplaySchedule.from_artifact(minimal_replay_artifact())
    changed = ReplaySchedule.from_artifact(
        minimal_replay_artifact(status=SimulationResultStatus.INCOMPLETE)
    )
    assert original.schedule_id != changed.schedule_id


def test_from_artifact_revalidates_typed_payload_linkage() -> None:
    artifact = _artifact()
    forged_market = artifact.market_events[0].model_copy(
        update={"source_record_id": "tampered-after-validation"}
    )
    forged = artifact.model_copy(
        update={"market_events": (forged_market, *artifact.market_events[1:])}
    )
    with pytest.raises(ValidationError, match="market event identity does not match"):
        DeterministicReplayScheduler.from_artifact(forged)


def test_content_identity_is_not_sufficient_checkpoint_trust() -> None:
    artifact = _artifact()
    schedule = ReplaySchedule.from_artifact(artifact)
    forged = _forged_checkpoint(schedule, 0)
    assert forged.checkpoint_id == calculate_replay_scheduler_checkpoint_id(forged)
    with pytest.raises(SchedulerCheckpointError, match="not issued"):
        DeterministicReplayScheduler.from_artifact(artifact, checkpoint=forged)
