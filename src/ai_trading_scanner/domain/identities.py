"""Strongly typed identifiers with shared syntax validation."""

import re
from typing import Self

from pydantic import ConfigDict, RootModel, field_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class Identifier(RootModel[str]):
    """Validated opaque identifier; it carries no authority or trading behavior."""

    model_config = ConfigDict(frozen=True)

    @field_validator("root")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("identifier cannot contain leading or trailing whitespace")
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError(
                "identifier must be 1-128 characters and use letters, digits, "
                "'.', '_', ':', '/', or '-'"
            )
        segments = value.replace(":", "/").split("/")
        if any(segment in {"", ".", ".."} for segment in segments):
            raise ValueError("identifier cannot contain empty or traversal segments")
        return value

    def __str__(self) -> str:
        return self.root

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.root!r})"

    @classmethod
    def parse(cls, value: str) -> Self:
        return cls.model_validate(value)


class AgentId(Identifier):
    """Identity of an isolated trading participant."""


class AccountId(Identifier):
    """Identity of a logically isolated account boundary."""


class AllocationId(Identifier):
    """Identity of an attributed capital allocation boundary."""


class ExperimentId(Identifier):
    """Identity of an immutable experiment run or registration."""


class StrategyId(Identifier):
    """Identity of a strategy independently from its model."""


class ModelId(Identifier):
    """Identity of an optional AI model independently from strategy."""


class ConfigurationVersionId(Identifier):
    """Identity of a versioned resolved configuration."""


class InstrumentId(Identifier):
    """Identity of a canonical tradable instrument."""


class DatasetId(Identifier):
    """Content-derived identity of an immutable market-data dataset."""


class IndicatorConfigurationId(Identifier):
    """Content-derived identity of an immutable indicator configuration."""


class StrategyConfigurationId(Identifier):
    """Content-derived identity of immutable strategy parameters."""


class StrategyDecisionId(Identifier):
    """Content-derived identity of one deterministic strategy decision."""


class TradeProposalId(Identifier):
    """Content-derived identity of immutable approval-sensitive trade intent."""


class ManagementMandateId(Identifier):
    """Content-derived identity of an immutable management mandate."""


class RiskConfigurationId(Identifier):
    """Content-derived identity of an immutable risk configuration."""


class RiskDecisionId(Identifier):
    """Content-derived identity of one deterministic risk evaluation."""


class SizingDecisionId(Identifier):
    """Content-derived identity of one deterministic sizing result."""


class ReservationId(Identifier):
    """Identity of one proposal-bound capital reservation contract."""


class SafetyLockId(Identifier):
    """Content-derived identity of an active safety lock."""


class LossStateId(Identifier):
    """Content-derived identity of an immutable loss-capacity observation."""


class SafetyStateId(Identifier):
    """Content-derived identity of one evaluated safety-state view."""


class ApprovalBindingId(Identifier):
    """Content-derived identity of immutable future approval evidence."""


class SimulationRunId(Identifier):
    """Content-derived identity of an immutable simulation run manifest."""


class SimulationExecutionModelId(Identifier):
    """Content-derived identity of a versioned simulation execution model."""


class TransactionCostModelId(Identifier):
    """Content-derived identity of a versioned transaction-cost model."""


class MarketEventId(Identifier):
    """Content-derived identity of a market event used during replay."""


class ReplayEventId(Identifier):
    """Content-derived identity of an ordered replay event envelope."""


class ReplayScheduleId(Identifier):
    """Content-derived identity of one canonical replay schedule."""


class ReplaySchedulerCheckpointId(Identifier):
    """Content-derived identity of one replay scheduler checkpoint."""


class OrchestrationConfigurationId(Identifier):
    """Content-derived identity of one causal orchestration configuration."""


class OrchestrationResultId(Identifier):
    """Content-derived identity of one causal orchestration evaluation."""


class ReplayArtifactId(Identifier):
    """Content-derived identity of one validated immutable replay artifact."""


class SimulatedOrderId(Identifier):
    """Content-derived identity of an immutable simulated order intent."""


class OrderCreationCommandId(Identifier):
    """Content-derived identity of one idempotent simulated-order command."""


class OrderCreationReceiptId(Identifier):
    """Content-derived identity of one simulated-order creation outcome."""


class OrderProjectionId(Identifier):
    """Content-derived identity of one immutable simulated-order projection."""


class OrderCancellationCommandId(Identifier):
    """Content-derived identity of one causally stamped cancellation command."""


class OrderTerminalResolutionId(Identifier):
    """Content-derived identity of one terminal simulated-order resolution."""


class SimulationLiquidityModelId(Identifier):
    """Content-derived identity of a deterministic simulation-liquidity profile."""


class SimulatedFillId(Identifier):
    """Content-derived identity of an immutable simulated fill."""


class PositionId(Identifier):
    """Identity of one long-only position episode."""


class PositionChangeId(Identifier):
    """Content-derived identity of an immutable position change."""


class PortfolioSnapshotId(Identifier):
    """Content-derived identity of an immutable portfolio snapshot."""


class RealizedTradeResultId(Identifier):
    """Content-derived identity of an immutable realized trade result."""


class SimulationResultId(Identifier):
    """Content-derived identity of an immutable simulation result."""


class CostProfileRegistrationId(Identifier):
    """Content-derived identity of one sourcing/audit record over a transaction-cost model."""


class FxObservationId(Identifier):
    """Content-derived identity of one immutable causal FX observation."""


class FxConversionPolicyId(Identifier):
    """Content-derived identity of a versioned, executable FX conversion policy."""


class FxValuationPolicyId(Identifier):
    """Content-derived identity of a versioned, reporting-only FX valuation policy."""


class FxConversionRequestId(Identifier):
    """Content-derived identity of one FX conversion request, independent of any trade proposal."""


class FxConversionReservationId(Identifier):
    """Content-derived identity of one FX-specific capital reservation contract."""


class FxConversionAuthorizationId(Identifier):
    """Content-derived identity of one authorization binding an FX
    conversion calculation to a reservation."""


class FxConversionPostingEvidenceId(Identifier):
    """Content-derived identity of one proposed FX conversion posting's evidence record."""
