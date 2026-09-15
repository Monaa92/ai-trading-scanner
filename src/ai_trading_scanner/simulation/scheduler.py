"""Deterministic, in-memory cursor over the authoritative Phase 6 event order."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_trading_scanner.domain import (
    ReplayEventId,
    ReplayScheduleId,
    ReplaySchedulerCheckpointId,
    SimulationRunId,
)
from ai_trading_scanner.domain.content_identity import sha256_content_id_v2
from ai_trading_scanner.simulation.artifacts import ReplayArtifactBundle
from ai_trading_scanner.simulation.models import (
    ReplayEvent,
    calculate_replay_trace_hash,
    order_replay_events,
    validate_replay_trace,
)


def _without_id(value: BaseModel | dict[str, object], field: str) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude={field})
    return {key: item for key, item in value.items() if key != field}


class ReplaySchedule(BaseModel):
    """Immutable canonical event sequence for exactly one simulation run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schedule_id: ReplayScheduleId
    schema_version: Literal["replay-schedule-v1"] = "replay-schedule-v1"
    run_id: SimulationRunId
    replay_trace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    events: tuple[ReplayEvent, ...] = Field(min_length=1)

    @classmethod
    def from_artifact(cls, artifact: ReplayArtifactBundle) -> ReplaySchedule:
        """Derive a schedule only after authoritative typed artifact validation."""
        validated = ReplayArtifactBundle.model_validate(artifact.model_dump(mode="python"))
        canonical_events = order_replay_events(validated.events)
        content: dict[str, object] = {
            "schema_version": "replay-schedule-v1",
            "run_id": validated.manifest.run_id,
            "replay_trace_sha256": calculate_replay_trace_hash(canonical_events),
            "events": canonical_events,
        }
        return cls.model_validate({"schedule_id": calculate_replay_schedule_id(content), **content})

    @model_validator(mode="after")
    def validate_schedule(self) -> Self:
        revalidated = tuple(
            ReplayEvent.model_validate(event.model_dump(mode="python")) for event in self.events
        )
        if revalidated != self.events:
            raise ValueError("replay schedule events differ after contract validation")
        validate_replay_trace(self.events)
        if any(event.run_id != self.run_id for event in self.events):
            raise ValueError("replay schedule contains an event from another run")
        if self.replay_trace_sha256 != calculate_replay_trace_hash(self.events):
            raise ValueError("replay schedule trace hash does not match its events")
        if self.schedule_id != calculate_replay_schedule_id(self):
            raise ValueError("replay schedule identity does not match content")
        return self


def calculate_replay_schedule_id(
    schedule: ReplaySchedule | dict[str, object],
) -> ReplayScheduleId:
    """Derive a schedule identity through the existing Phase 6 V2 primitive."""
    return ReplayScheduleId.parse(sha256_content_id_v2(_without_id(schedule, "schedule_id")))


class ReplaySchedulerCheckpoint(BaseModel):
    """Immutable resume evidence bound to one exact canonical schedule prefix."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    checkpoint_id: ReplaySchedulerCheckpointId
    schema_version: Literal["replay-scheduler-checkpoint-v1"] = "replay-scheduler-checkpoint-v1"
    schedule_id: ReplayScheduleId
    run_id: SimulationRunId
    next_position: int = Field(ge=0)
    total_events: int = Field(gt=0)
    consumed_event_ids: tuple[ReplayEventId, ...] = ()
    next_event_id: ReplayEventId | None

    @model_validator(mode="after")
    def validate_checkpoint(self) -> Self:
        if self.next_position > self.total_events:
            raise ValueError("scheduler checkpoint position exceeds its schedule length")
        if len(self.consumed_event_ids) != self.next_position:
            raise ValueError("scheduler checkpoint does not contain its exact consumed prefix")
        if len(set(self.consumed_event_ids)) != len(self.consumed_event_ids):
            raise ValueError("scheduler checkpoint contains duplicate consumed events")
        exhausted = self.next_position == self.total_events
        if exhausted != (self.next_event_id is None):
            raise ValueError("scheduler checkpoint next event is inconsistent with exhaustion")
        if self.checkpoint_id != calculate_replay_scheduler_checkpoint_id(self):
            raise ValueError("scheduler checkpoint identity does not match content")
        return self

    def validate_for(self, schedule: ReplaySchedule) -> None:
        """Prove that this state is an unskipped prefix of the supplied schedule."""
        expected = _checkpoint_at(schedule, self.next_position)
        if self != expected:
            raise SchedulerCheckpointError(
                "scheduler checkpoint belongs to another schedule or state"
            )


def calculate_replay_scheduler_checkpoint_id(
    checkpoint: ReplaySchedulerCheckpoint | dict[str, object],
) -> ReplaySchedulerCheckpointId:
    """Derive checkpoint identity through the existing Phase 6 V2 primitive."""
    return ReplaySchedulerCheckpointId.parse(
        sha256_content_id_v2(_without_id(checkpoint, "checkpoint_id"))
    )


class SchedulerCheckpointError(ValueError):
    """Raised when resume evidence cannot be applied to the requested schedule."""


class SchedulerExhaustedError(RuntimeError):
    """Raised when a caller attempts to consume beyond deterministic exhaustion."""


@dataclass(slots=True)
class _TrustedCursorState:
    """Process-local authority for one logical cursor over one exact schedule."""

    schedule_id: ReplayScheduleId
    run_id: SimulationRunId
    total_events: int
    next_position: int
    trusted_checkpoint_id: ReplaySchedulerCheckpointId | None
    lock: Lock


_PROCESS_CURSOR_STATES: dict[ReplayScheduleId, _TrustedCursorState] = {}
_PROCESS_CURSOR_STATES_LOCK = Lock()


def _checkpoint_at(schedule: ReplaySchedule, next_position: int) -> ReplaySchedulerCheckpoint:
    """Build structural checkpoint content; this function does not grant resume trust."""
    if next_position < 0 or next_position > len(schedule.events):
        raise ValueError("scheduler checkpoint position is outside the schedule")
    content: dict[str, object] = {
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
    return ReplaySchedulerCheckpoint.model_validate(
        {"checkpoint_id": calculate_replay_scheduler_checkpoint_id(content), **content}
    )


def _trusted_state_for(schedule: ReplaySchedule) -> _TrustedCursorState:
    """Return the single process-local cursor authority for an exact schedule."""
    with _PROCESS_CURSOR_STATES_LOCK:
        state = _PROCESS_CURSOR_STATES.get(schedule.schedule_id)
        if state is None:
            state = _TrustedCursorState(
                schedule_id=schedule.schedule_id,
                run_id=schedule.run_id,
                total_events=len(schedule.events),
                next_position=0,
                trusted_checkpoint_id=None,
                lock=Lock(),
            )
            _PROCESS_CURSOR_STATES[schedule.schedule_id] = state
            return state
        if state.run_id != schedule.run_id or state.total_events != len(schedule.events):
            raise SchedulerCheckpointError("scheduler authority conflicts with schedule identity")
        return state


class DeterministicReplayScheduler:
    """Tightly controlled one-step cursor; it performs no replay side effects."""

    __slots__ = ("_schedule", "_state")

    def __init__(
        self,
        artifact: ReplayArtifactBundle,
        checkpoint: ReplaySchedulerCheckpoint | None = None,
    ) -> None:
        if not isinstance(artifact, ReplayArtifactBundle):
            raise TypeError("executable scheduler construction requires ReplayArtifactBundle")
        validated_artifact = ReplayArtifactBundle.model_validate(artifact.model_dump(mode="python"))
        self._schedule = ReplaySchedule.from_artifact(validated_artifact)
        self._state = _trusted_state_for(self._schedule)
        if checkpoint is not None:
            validated_checkpoint = ReplaySchedulerCheckpoint.model_validate(
                checkpoint.model_dump(mode="python")
            )
            validated_checkpoint.validate_for(self._schedule)
            with self._state.lock:
                if (
                    self._state.trusted_checkpoint_id != validated_checkpoint.checkpoint_id
                    or self._state.next_position != validated_checkpoint.next_position
                ):
                    raise SchedulerCheckpointError(
                        "scheduler checkpoint was not issued from current process-local state"
                    )

    @classmethod
    def from_artifact(
        cls,
        artifact: ReplayArtifactBundle,
        *,
        checkpoint: ReplaySchedulerCheckpoint | None = None,
    ) -> DeterministicReplayScheduler:
        return cls(artifact, checkpoint)

    @property
    def schedule(self) -> ReplaySchedule:
        return self._schedule

    @property
    def schedule_id(self) -> ReplayScheduleId:
        return self._schedule.schedule_id

    @property
    def run_id(self) -> SimulationRunId:
        return self._schedule.run_id

    @property
    def position(self) -> int:
        """Index of the next event; it advances by exactly one per consumption."""
        with self._state.lock:
            return self._state.next_position

    @property
    def remaining(self) -> int:
        with self._state.lock:
            return len(self._schedule.events) - self._state.next_position

    @property
    def has_events(self) -> bool:
        with self._state.lock:
            return self._state.next_position < len(self._schedule.events)

    @property
    def exhausted(self) -> bool:
        return not self.has_events

    @property
    def state(self) -> ReplaySchedulerCheckpoint:
        return self.checkpoint()

    def checkpoint(self) -> ReplaySchedulerCheckpoint:
        with self._state.lock:
            checkpoint = _checkpoint_at(self._schedule, self._state.next_position)
            self._state.trusted_checkpoint_id = checkpoint.checkpoint_id
            return checkpoint

    def peek_next(self) -> ReplayEvent:
        with self._state.lock:
            if self._state.next_position >= len(self._schedule.events):
                raise SchedulerExhaustedError("replay schedule is exhausted")
            return self._schedule.events[self._state.next_position]

    def next_event(self) -> ReplayEvent:
        with self._state.lock:
            if self._state.next_position >= len(self._schedule.events):
                raise SchedulerExhaustedError("replay schedule is exhausted")
            event = self._schedule.events[self._state.next_position]
            self._state.next_position += 1
            self._state.trusted_checkpoint_id = None
            return event
