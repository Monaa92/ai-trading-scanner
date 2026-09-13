"""Phase 1 startup configuration and safety policy."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from ai_trading_scanner.domain.execution import (
    ExecutionDimensions,
    ExecutionEnvironment,
    OperatingContext,
    SubmissionMode,
)
from ai_trading_scanner.domain.identities import ConfigurationVersionId


class Phase1Safety(BaseModel):
    """Capabilities that are intentionally impossible in the offline foundation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    live_trading_enabled: Literal[False]
    paper_order_submission_enabled: Literal[False]
    broker_connections_enabled: Literal[False]
    external_service_calls_enabled: Literal[False]
    ai_inference_enabled: Literal[False]


class FoundationConfig(BaseModel):
    """Complete configuration accepted by the Phase 1 executable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["phase1-v1"]
    configuration_version_id: ConfigurationVersionId
    execution: ExecutionDimensions
    safety: Phase1Safety

    @model_validator(mode="after")
    def enforce_phase1_boundary(self) -> Self:
        if self.execution.execution_environment is ExecutionEnvironment.LIVE:
            raise ValueError("LIVE operational activation is disabled in Phase 1")
        if self.execution.submission_mode is not SubmissionMode.SIGNAL_ONLY:
            raise ValueError("Phase 1 supports SIGNAL_ONLY only; order submission is unavailable")
        if self.execution.operating_context is OperatingContext.EXPERIMENT:
            raise ValueError("experiment execution is not implemented in Phase 1")
        return self
