"""Independent execution dimensions defined by ADR-018."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from ai_trading_scanner.domain.identities import ExperimentId


class DataRunMode(StrEnum):
    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"
    LIVE_FEED = "LIVE_FEED"
    CAPTURED_REPLAY = "CAPTURED_REPLAY"


class ExecutionEnvironment(StrEnum):
    SIMULATION = "SIMULATION"
    PAPER = "PAPER"
    LIVE = "LIVE"


class SubmissionMode(StrEnum):
    SIGNAL_ONLY = "SIGNAL_ONLY"
    ORDER_ENABLED = "ORDER_ENABLED"


class ApprovalPolicy(StrEnum):
    MANUAL_APPROVAL = "MANUAL_APPROVAL"
    FULL_AUTO = "FULL_AUTO"


class OperatingContext(StrEnum):
    NORMAL = "NORMAL"
    EXPERIMENT = "EXPERIMENT"


class ExperimentType(StrEnum):
    AUTONOMOUS_EXPERIMENT = "AUTONOMOUS_EXPERIMENT"


class ExecutionDimensions(BaseModel):
    """Domain representation; it grants no operational capability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data_run_mode: DataRunMode
    execution_environment: ExecutionEnvironment
    submission_mode: SubmissionMode
    approval_policy: ApprovalPolicy
    operating_context: OperatingContext
    experiment_id: ExperimentId | None = None
    experiment_type: ExperimentType | None = None

    @model_validator(mode="after")
    def validate_experiment_identity(self) -> Self:
        if self.operating_context is OperatingContext.EXPERIMENT and self.experiment_id is None:
            raise ValueError("EXPERIMENT context requires experiment_id")
        if self.operating_context is OperatingContext.NORMAL and (
            self.experiment_id is not None or self.experiment_type is not None
        ):
            raise ValueError("NORMAL context cannot carry experiment identity or type")
        return self
