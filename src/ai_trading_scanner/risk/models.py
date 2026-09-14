"""Immutable Phase 5 risk, sizing, ownership, lock, and reservation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_FLOOR, Context, Decimal, localcontext
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_trading_scanner.domain import (
    AccountId,
    AgentId,
    AllocationId,
    ApprovalBindingId,
    ConfigurationVersionId,
    InstrumentId,
    LossStateId,
    ManagementMandateId,
    ReservationId,
    RiskConfigurationId,
    RiskDecisionId,
    SafetyLockId,
    SafetyStateId,
    SizingDecisionId,
    TradeProposalId,
)
from ai_trading_scanner.domain.content_identity import sha256_content_id
from ai_trading_scanner.domain.execution import (
    ApprovalPolicy,
    ExecutionDimensions,
    ExecutionEnvironment,
)
from ai_trading_scanner.strategies import ProposalSide, SizingMethod, TradeProposal


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _content_without_id(value: BaseModel | dict[str, object], field: str) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude={field})
    return {key: item for key, item in value.items() if key != field}


_DECIMAL_CONTEXT = Context(prec=34)


class RiskPolicyStatus(StrEnum):
    RESEARCH_ONLY = "RESEARCH_ONLY"


class RiskConfiguration(BaseModel):
    """Versioned risk limits; this contract grants no execution authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    risk_configuration_id: RiskConfigurationId
    schema_version: Literal["risk-configuration-v1"] = "risk-configuration-v1"
    profile_name: str = Field(min_length=1, pattern=r"^[A-Z][A-Z0-9_]*$")
    profile_version: str = Field(min_length=1)
    status: Literal[RiskPolicyStatus.RESEARCH_ONLY] = RiskPolicyStatus.RESEARCH_ONLY
    authority_configuration_version_id: ConfigurationVersionId
    max_risk_fraction: Annotated[Decimal, Field(gt=0, le=1, allow_inf_nan=False)]
    max_monetary_risk: Annotated[Decimal | None, Field(gt=0, allow_inf_nan=False)] = None
    max_position_fraction: Annotated[Decimal, Field(gt=0, le=1, allow_inf_nan=False)]
    max_agent_exposure_fraction: Annotated[Decimal, Field(gt=0, le=1, allow_inf_nan=False)]
    max_parent_exposure_fraction: Annotated[Decimal, Field(gt=0, le=1, allow_inf_nan=False)]
    max_instrument_exposure_fraction: Annotated[Decimal, Field(gt=0, le=1, allow_inf_nan=False)]
    max_agent_drawdown_fraction: Annotated[Decimal, Field(gt=0, le=1, allow_inf_nan=False)]
    max_parent_drawdown_fraction: Annotated[Decimal, Field(gt=0, le=1, allow_inf_nan=False)]
    max_concurrent_reservations: Annotated[int, Field(gt=0)]
    quantity_increment: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    max_proposal_age_seconds: Annotated[int, Field(gt=0)]
    allowed_execution_environments: tuple[ExecutionEnvironment, ...] = Field(min_length=1)
    allowed_approval_policies: tuple[ApprovalPolicy, ...] = Field(min_length=1)
    protective_stop_required: Literal[True] = True
    long_only: Literal[True] = True

    @model_validator(mode="before")
    @classmethod
    def reject_float_financial_inputs(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        decimal_fields = {
            "max_risk_fraction",
            "max_monetary_risk",
            "max_position_fraction",
            "max_agent_exposure_fraction",
            "max_parent_exposure_fraction",
            "max_instrument_exposure_fraction",
            "max_agent_drawdown_fraction",
            "max_parent_drawdown_fraction",
            "quantity_increment",
        }
        if any(isinstance(data.get(field), float) for field in decimal_fields):
            raise ValueError("risk financial values must not use float")
        return data

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if ExecutionEnvironment.LIVE in self.allowed_execution_environments:
            raise ValueError("Phase 5 risk configuration cannot enable LIVE")
        environments = tuple(
            sorted(set(self.allowed_execution_environments), key=lambda item: item.value)
        )
        policies = tuple(sorted(set(self.allowed_approval_policies), key=lambda item: item.value))
        if environments != self.allowed_execution_environments:
            raise ValueError("allowed execution environments must be unique and canonical")
        if policies != self.allowed_approval_policies:
            raise ValueError("allowed approval policies must be unique and canonical")
        if self.risk_configuration_id != calculate_risk_configuration_id(self):
            raise ValueError("risk configuration identity does not match content")
        return self


def calculate_risk_configuration_id(
    configuration: RiskConfiguration | dict[str, object],
) -> RiskConfigurationId:
    return RiskConfigurationId.parse(
        sha256_content_id(_content_without_id(configuration, "risk_configuration_id"))
    )


def baseline_risk_configuration(
    authority_configuration_version_id: ConfigurationVersionId,
) -> RiskConfiguration:
    """Create the unvalidated research-only EUR50-era risk profile."""
    content: dict[str, object] = {
        "schema_version": "risk-configuration-v1",
        "profile_name": "BASELINE_RESEARCH_V1",
        "profile_version": "0.1.0",
        "status": RiskPolicyStatus.RESEARCH_ONLY,
        "authority_configuration_version_id": authority_configuration_version_id,
        "max_risk_fraction": Decimal("0.01"),
        "max_monetary_risk": None,
        "max_position_fraction": Decimal("1"),
        "max_agent_exposure_fraction": Decimal("1"),
        "max_parent_exposure_fraction": Decimal("1"),
        "max_instrument_exposure_fraction": Decimal("1"),
        "max_agent_drawdown_fraction": Decimal("0.03"),
        "max_parent_drawdown_fraction": Decimal("0.03"),
        "max_concurrent_reservations": 1,
        "quantity_increment": Decimal("0.0001"),
        "max_proposal_age_seconds": 600,
        "allowed_execution_environments": (ExecutionEnvironment.SIMULATION,),
        "allowed_approval_policies": (
            ApprovalPolicy.FULL_AUTO,
            ApprovalPolicy.MANUAL_APPROVAL,
        ),
        "protective_stop_required": True,
        "long_only": True,
    }
    return RiskConfiguration(
        risk_configuration_id=calculate_risk_configuration_id(content),
        **content,  # type: ignore[arg-type]
    )


class ParentCapitalSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    account_id: AccountId
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    total_capital: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    available_capital: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    active_reserved_capital: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)] = Decimal(0)
    committed_capital: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)] = Decimal(0)
    revision: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode="before")
    @classmethod
    def reject_float_values(cls, data: object) -> object:
        if isinstance(data, dict) and any(
            isinstance(data.get(field), float)
            for field in (
                "total_capital",
                "available_capital",
                "active_reserved_capital",
                "committed_capital",
            )
        ):
            raise ValueError("capital values must not use float")
        return data

    @model_validator(mode="after")
    def validate_conservation(self) -> Self:
        if self.total_capital != (
            self.available_capital + self.active_reserved_capital + self.committed_capital
        ):
            raise ValueError("parent capital conservation failed")
        return self


class AllocationSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allocation_id: AllocationId
    account_id: AccountId
    agent_id: AgentId
    configuration_version_id: ConfigurationVersionId
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    allocated_capital: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    available_capital: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    active_reserved_capital: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)] = Decimal(0)
    committed_capital: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)] = Decimal(0)
    instrument_committed_capital: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)] = Decimal(0)
    active_reservation_count: Annotated[int, Field(ge=0)] = 0
    revision: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode="before")
    @classmethod
    def reject_float_values(cls, data: object) -> object:
        if isinstance(data, dict) and any(
            isinstance(data.get(field), float)
            for field in (
                "allocated_capital",
                "available_capital",
                "active_reserved_capital",
                "committed_capital",
                "instrument_committed_capital",
            )
        ):
            raise ValueError("allocation values must not use float")
        return data

    @model_validator(mode="after")
    def validate_conservation(self) -> Self:
        if self.allocated_capital != (
            self.available_capital + self.active_reserved_capital + self.committed_capital
        ):
            raise ValueError("allocation capital conservation failed")
        if self.instrument_committed_capital > self.committed_capital:
            raise ValueError("instrument exposure cannot exceed committed capital")
        return self


class SafetyLockScope(StrEnum):
    PARENT_ACCOUNT = "PARENT_ACCOUNT"
    ALLOCATION = "ALLOCATION"
    AGENT = "AGENT"


class SafetyLockReason(StrEnum):
    TRADING_LOCK = "TRADING_LOCK"
    DRAWDOWN_LOCK = "DRAWDOWN_LOCK"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    ADMINISTRATIVE_LOCK = "ADMINISTRATIVE_LOCK"
    RECONCILIATION_LOCK = "RECONCILIATION_LOCK"


class LossStateScope(StrEnum):
    PARENT_ACCOUNT = "PARENT_ACCOUNT"
    AGENT_ALLOCATION = "AGENT_ALLOCATION"


class SafetyLock(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    lock_id: SafetyLockId
    schema_version: Literal["safety-lock-v1"] = "safety-lock-v1"
    scope: SafetyLockScope
    reason: SafetyLockReason
    account_id: AccountId
    allocation_id: AllocationId | None = None
    agent_id: AgentId | None = None
    activated_at: datetime
    active: Literal[True] = True

    @field_validator("activated_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_scope_and_identity(self) -> Self:
        if self.scope is SafetyLockScope.PARENT_ACCOUNT and (
            self.allocation_id is not None or self.agent_id is not None
        ):
            raise ValueError("parent lock cannot carry allocation or agent identity")
        if self.scope is SafetyLockScope.ALLOCATION and self.allocation_id is None:
            raise ValueError("allocation lock requires allocation identity")
        if self.scope is SafetyLockScope.AGENT and (
            self.allocation_id is None or self.agent_id is None
        ):
            raise ValueError("agent lock requires allocation and agent identity")
        if self.lock_id != calculate_safety_lock_id(self):
            raise ValueError("safety lock identity does not match content")
        return self


def calculate_safety_lock_id(lock: SafetyLock | dict[str, object]) -> SafetyLockId:
    return SafetyLockId.parse(sha256_content_id(_content_without_id(lock, "lock_id")))


def create_safety_lock(
    *,
    scope: SafetyLockScope,
    reason: SafetyLockReason,
    account_id: AccountId,
    activated_at: datetime,
    allocation_id: AllocationId | None = None,
    agent_id: AgentId | None = None,
) -> SafetyLock:
    content: dict[str, object] = {
        "schema_version": "safety-lock-v1",
        "scope": scope,
        "reason": reason,
        "account_id": account_id,
        "allocation_id": allocation_id,
        "agent_id": agent_id,
        "activated_at": _aware_utc(activated_at),
        "active": True,
    }
    return SafetyLock(
        lock_id=calculate_safety_lock_id(content),
        **content,  # type: ignore[arg-type]
    )


class LossStateSnapshot(BaseModel):
    """Externally calculated current-equity and daily-loss evidence for one scope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    loss_state_id: LossStateId
    schema_version: Literal["loss-state-v2"] = "loss-state-v2"
    scope: LossStateScope
    account_id: AccountId
    allocation_id: AllocationId | None = None
    agent_id: AgentId | None = None
    session_id: str = Field(min_length=1)
    session_start_at: datetime
    session_end_at: datetime
    observed_at: datetime
    effective_at: datetime
    valid_until: datetime
    eligible_current_equity: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    session_start_equity: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    current_loss: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    loss_breached: bool = False
    revision: Annotated[int, Field(ge=0)] = 0

    @field_validator(
        "session_start_at",
        "session_end_at",
        "observed_at",
        "effective_at",
        "valid_until",
    )
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="before")
    @classmethod
    def reject_float_values(cls, data: object) -> object:
        if isinstance(data, dict) and any(
            isinstance(data.get(field), float)
            for field in (
                "eligible_current_equity",
                "session_start_equity",
                "current_loss",
            )
        ):
            raise ValueError("loss-state financial values must not use float")
        return data

    @model_validator(mode="after")
    def validate_loss_state(self) -> Self:
        if self.scope is LossStateScope.PARENT_ACCOUNT:
            if self.allocation_id is not None or self.agent_id is not None:
                raise ValueError("parent loss state cannot carry allocation or agent identity")
        elif self.allocation_id is None or self.agent_id is None:
            raise ValueError("agent-allocation loss state requires allocation and agent identity")
        if not (
            self.session_start_at
            <= self.effective_at
            <= self.observed_at
            < self.valid_until
            <= self.session_end_at
        ):
            raise ValueError("loss-state timestamps violate causal or freshness ordering")
        with localcontext(_DECIMAL_CONTEXT):
            expected_loss = max(
                Decimal(0), self.session_start_equity - self.eligible_current_equity
            )
        if self.current_loss != expected_loss:
            raise ValueError("current loss must equal session-start minus eligible equity")
        if self.loss_state_id != calculate_loss_state_id(self):
            raise ValueError("loss state identity does not match content")
        return self


def calculate_loss_state_id(
    state: LossStateSnapshot | dict[str, object],
) -> LossStateId:
    return LossStateId.parse(sha256_content_id(_content_without_id(state, "loss_state_id")))


def create_loss_state(
    *,
    scope: LossStateScope,
    account_id: AccountId,
    session_id: str,
    session_start_at: datetime,
    session_end_at: datetime,
    observed_at: datetime,
    effective_at: datetime,
    valid_until: datetime,
    eligible_current_equity: Decimal,
    session_start_equity: Decimal,
    current_loss: Decimal,
    allocation_id: AllocationId | None = None,
    agent_id: AgentId | None = None,
    loss_breached: bool = False,
    revision: int = 0,
) -> LossStateSnapshot:
    content: dict[str, object] = {
        "schema_version": "loss-state-v2",
        "scope": scope,
        "account_id": account_id,
        "allocation_id": allocation_id,
        "agent_id": agent_id,
        "session_id": session_id,
        "session_start_at": _aware_utc(session_start_at),
        "session_end_at": _aware_utc(session_end_at),
        "observed_at": _aware_utc(observed_at),
        "effective_at": _aware_utc(effective_at),
        "valid_until": _aware_utc(valid_until),
        "eligible_current_equity": eligible_current_equity,
        "session_start_equity": session_start_equity,
        "current_loss": current_loss,
        "loss_breached": loss_breached,
        "revision": revision,
    }
    return LossStateSnapshot(
        loss_state_id=calculate_loss_state_id(content),
        **content,  # type: ignore[arg-type]
    )


class SafetyStateSnapshot(BaseModel):
    """Canonical safety view composed from explicit loss state, downside, and locks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    safety_state_id: SafetyStateId
    schema_version: Literal["safety-state-v2"] = "safety-state-v2"
    agent_loss_state: LossStateSnapshot
    parent_loss_state: LossStateSnapshot
    agent_outstanding_downside: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    parent_outstanding_downside: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    active_locks: tuple[SafetyLock, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def reject_float_values(cls, data: object) -> object:
        if isinstance(data, dict) and any(
            isinstance(data.get(field), float)
            for field in ("agent_outstanding_downside", "parent_outstanding_downside")
        ):
            raise ValueError("safety-state financial values must not use float")
        return data

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        ordered = tuple(sorted(self.active_locks, key=lambda item: str(item.lock_id)))
        if ordered != self.active_locks or len(set(self.active_locks)) != len(self.active_locks):
            raise ValueError("active locks must be unique and canonical")
        if self.agent_outstanding_downside > self.parent_outstanding_downside:
            raise ValueError("agent downside cannot exceed parent downside")
        if self.safety_state_id != calculate_safety_state_id(self):
            raise ValueError("safety state identity does not match content")
        return self


def calculate_safety_state_id(
    state: SafetyStateSnapshot | dict[str, object],
) -> SafetyStateId:
    return SafetyStateId.parse(sha256_content_id(_content_without_id(state, "safety_state_id")))


def create_safety_state(
    *,
    agent_loss_state: LossStateSnapshot,
    parent_loss_state: LossStateSnapshot,
    agent_outstanding_downside: Decimal = Decimal(0),
    parent_outstanding_downside: Decimal = Decimal(0),
    active_locks: tuple[SafetyLock, ...] = (),
) -> SafetyStateSnapshot:
    content: dict[str, object] = {
        "schema_version": "safety-state-v2",
        "agent_loss_state": agent_loss_state,
        "parent_loss_state": parent_loss_state,
        "agent_outstanding_downside": agent_outstanding_downside,
        "parent_outstanding_downside": parent_outstanding_downside,
        "active_locks": active_locks,
    }
    return SafetyStateSnapshot(
        safety_state_id=calculate_safety_state_id(content),
        **content,  # type: ignore[arg-type]
    )


class RiskEvaluationState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    parent: ParentCapitalSnapshot
    allocation: AllocationSnapshot
    safety: SafetyStateSnapshot

    @model_validator(mode="after")
    def validate_ownership(self) -> Self:
        if self.allocation.account_id != self.parent.account_id:
            raise ValueError("allocation does not belong to parent account")
        parent_loss = self.safety.parent_loss_state
        agent_loss = self.safety.agent_loss_state
        if (
            parent_loss.scope is not LossStateScope.PARENT_ACCOUNT
            or parent_loss.account_id != self.parent.account_id
        ):
            raise ValueError("parent loss state attribution does not match parent account")
        if (
            agent_loss.scope is not LossStateScope.AGENT_ALLOCATION
            or agent_loss.account_id != self.parent.account_id
            or agent_loss.allocation_id != self.allocation.allocation_id
            or agent_loss.agent_id != self.allocation.agent_id
        ):
            raise ValueError("agent loss state attribution does not match allocation owner")
        if (
            agent_loss.session_id != parent_loss.session_id
            or agent_loss.session_start_at != parent_loss.session_start_at
            or agent_loss.session_end_at != parent_loss.session_end_at
        ):
            raise ValueError("agent and parent loss states must share one session boundary")
        for lock in self.safety.active_locks:
            if lock.account_id != self.parent.account_id:
                raise ValueError("safety lock belongs to a different parent account")
            if lock.scope is SafetyLockScope.ALLOCATION and (
                lock.allocation_id != self.allocation.allocation_id
            ):
                raise ValueError("allocation safety lock is not applicable")
            if lock.scope is SafetyLockScope.AGENT and (
                lock.allocation_id != self.allocation.allocation_id
                or lock.agent_id != self.allocation.agent_id
            ):
                raise ValueError("agent safety lock is not applicable")
        return self


@dataclass(frozen=True, slots=True)
class _SizingDerivation:
    unit_risk: Decimal
    round_trip_cost_return: Decimal
    unit_modeled_loss: Decimal
    agent_daily_loss_ceiling: Decimal
    parent_daily_loss_ceiling: Decimal
    agent_remaining_loss_headroom: Decimal
    parent_remaining_loss_headroom: Decimal
    allowed_risk_amount: Decimal
    cash_per_unit: Decimal
    position_headroom: Decimal
    agent_headroom: Decimal
    parent_headroom: Decimal
    instrument_headroom: Decimal
    available_capital: Decimal
    raw_quantity: Decimal
    quantity: Decimal
    modeled_risk_amount: Decimal
    reservation_amount: Decimal


def _loss_capacity(
    configuration: RiskConfiguration,
    state: RiskEvaluationState,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    agent = state.safety.agent_loss_state
    parent = state.safety.parent_loss_state
    with localcontext(_DECIMAL_CONTEXT):
        agent_ceiling = configuration.max_agent_drawdown_fraction * min(
            agent.session_start_equity, agent.eligible_current_equity
        )
        parent_ceiling = configuration.max_parent_drawdown_fraction * min(
            parent.session_start_equity, parent.eligible_current_equity
        )
        agent_remaining = max(
            Decimal(0),
            agent_ceiling - agent.current_loss - state.safety.agent_outstanding_downside,
        )
        parent_remaining = max(
            Decimal(0),
            parent_ceiling - parent.current_loss - state.safety.parent_outstanding_downside,
        )
    return agent_ceiling, parent_ceiling, agent_remaining, parent_remaining


def _derive_sizing(
    proposal: TradeProposal,
    configuration: RiskConfiguration,
    state: RiskEvaluationState,
) -> _SizingDerivation:
    allocation = state.allocation
    parent = state.parent
    entry = proposal.entry.reference_price
    stop = proposal.stop_level
    with localcontext(_DECIMAL_CONTEXT):
        unit_risk = entry - stop
        if unit_risk <= 0:
            raise ValueError("long stop must remain below entry")
        cost_return = proposal.economics.cost_estimate.total_return_drag
        unit_modeled_loss = unit_risk + entry * cost_return
        agent_ceiling, parent_ceiling, agent_remaining, parent_remaining = _loss_capacity(
            configuration, state
        )
        risk_budget = (
            state.safety.agent_loss_state.eligible_current_equity * configuration.max_risk_fraction
        )
        if configuration.max_monetary_risk is not None:
            risk_budget = min(risk_budget, configuration.max_monetary_risk)
        risk_budget = min(risk_budget, agent_remaining, parent_remaining)
        cash_per_unit = entry * (Decimal(1) + cost_return)
        position_headroom = allocation.allocated_capital * configuration.max_position_fraction
        agent_headroom = (
            allocation.allocated_capital * configuration.max_agent_exposure_fraction
            - allocation.active_reserved_capital
            - allocation.committed_capital
        )
        parent_headroom = (
            parent.total_capital * configuration.max_parent_exposure_fraction
            - parent.active_reserved_capital
            - parent.committed_capital
        )
        instrument_headroom = (
            allocation.allocated_capital * configuration.max_instrument_exposure_fraction
            - allocation.instrument_committed_capital
            - allocation.active_reserved_capital
        )
        available = min(allocation.available_capital, parent.available_capital)
        raw_quantity = min(
            risk_budget / unit_modeled_loss,
            available / cash_per_unit,
            position_headroom / cash_per_unit,
            max(agent_headroom, Decimal(0)) / cash_per_unit,
            max(parent_headroom, Decimal(0)) / cash_per_unit,
            max(instrument_headroom, Decimal(0)) / cash_per_unit,
        )
        if proposal.sizing.method is SizingMethod.FINAL_QUANTITY:
            assert proposal.sizing.final_quantity is not None
            quantity = proposal.sizing.final_quantity
        else:
            units = (raw_quantity / configuration.quantity_increment).to_integral_value(
                rounding=ROUND_FLOOR
            )
            quantity = units * configuration.quantity_increment
        modeled_risk = quantity * unit_modeled_loss
        reservation_amount = quantity * cash_per_unit
    return _SizingDerivation(
        unit_risk=unit_risk,
        round_trip_cost_return=cost_return,
        unit_modeled_loss=unit_modeled_loss,
        agent_daily_loss_ceiling=agent_ceiling,
        parent_daily_loss_ceiling=parent_ceiling,
        agent_remaining_loss_headroom=agent_remaining,
        parent_remaining_loss_headroom=parent_remaining,
        allowed_risk_amount=risk_budget,
        cash_per_unit=cash_per_unit,
        position_headroom=position_headroom,
        agent_headroom=agent_headroom,
        parent_headroom=parent_headroom,
        instrument_headroom=instrument_headroom,
        available_capital=available,
        raw_quantity=raw_quantity,
        quantity=quantity,
        modeled_risk_amount=modeled_risk,
        reservation_amount=reservation_amount,
    )


class SizingDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sizing_decision_id: SizingDecisionId
    schema_version: Literal["sizing-decision-v4"] = "sizing-decision-v4"
    proposal_id: TradeProposalId
    risk_configuration_id: RiskConfigurationId
    source_proposal: TradeProposal
    source_risk_configuration: RiskConfiguration
    source_evaluation_state: RiskEvaluationState
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    quantity: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    quantity_increment: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    entry_price: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    stop_price: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    unit_risk: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    round_trip_cost_return: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    unit_modeled_loss: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    cash_per_unit: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    allowed_risk_amount: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    modeled_risk_amount: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    reservation_amount: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")

    @model_validator(mode="before")
    @classmethod
    def reject_float_values(cls, data: object) -> object:
        if isinstance(data, dict) and any(
            isinstance(data.get(field), float)
            for field in (
                "quantity",
                "quantity_increment",
                "entry_price",
                "stop_price",
                "unit_risk",
                "round_trip_cost_return",
                "unit_modeled_loss",
                "cash_per_unit",
                "allowed_risk_amount",
                "modeled_risk_amount",
                "reservation_amount",
            )
        ):
            raise ValueError("sizing values must not use float")
        return data

    @model_validator(mode="after")
    def validate_sizing(self) -> Self:
        proposal = self.source_proposal
        configuration = self.source_risk_configuration
        state = self.source_evaluation_state
        if proposal.proposal_id != self.proposal_id:
            raise ValueError("sizing source proposal does not match proposal identity")
        if configuration.risk_configuration_id != self.risk_configuration_id:
            raise ValueError("sizing source configuration does not match configuration identity")
        if proposal.agent_id != self.agent_id:
            raise ValueError("sizing source proposal does not match agent attribution")
        if (
            state.parent.account_id != self.account_id
            or state.allocation.account_id != self.account_id
            or state.allocation.allocation_id != self.allocation_id
            or state.allocation.agent_id != self.agent_id
        ):
            raise ValueError("sizing source state does not match ownership attribution")
        if (
            proposal.authority_context.configuration_version_id
            != configuration.authority_configuration_version_id
            or state.allocation.configuration_version_id
            != configuration.authority_configuration_version_id
        ):
            raise ValueError("sizing source authority differs from risk configuration")
        if (
            proposal.entry.currency != state.parent.currency
            or proposal.entry.currency != state.allocation.currency
        ):
            raise ValueError("sizing source currencies are inconsistent")
        if (
            self.entry_price != proposal.entry.reference_price
            or self.stop_price != proposal.stop_level
            or self.currency != proposal.entry.currency
            or self.round_trip_cost_return != proposal.economics.cost_estimate.total_return_drag
        ):
            raise ValueError("sizing values do not match immutable proposal content")
        if self.quantity_increment != configuration.quantity_increment:
            raise ValueError("sizing increment does not match immutable risk configuration")
        if (
            proposal.sizing.method is SizingMethod.FINAL_QUANTITY
            and self.quantity != proposal.sizing.final_quantity
        ):
            raise ValueError("sizing quantity does not match immutable final-quantity intent")
        derived = _derive_sizing(proposal, configuration, state)
        if (
            self.quantity != derived.quantity
            or self.unit_risk != derived.unit_risk
            or self.round_trip_cost_return != derived.round_trip_cost_return
            or self.unit_modeled_loss != derived.unit_modeled_loss
            or self.cash_per_unit != derived.cash_per_unit
            or self.allowed_risk_amount != derived.allowed_risk_amount
            or self.modeled_risk_amount != derived.modeled_risk_amount
            or self.reservation_amount != derived.reservation_amount
        ):
            raise ValueError("sizing values are not the deterministic result of bound inputs")
        with localcontext(_DECIMAL_CONTEXT):
            if self.quantity % self.quantity_increment != 0:
                raise ValueError("quantity must align to quantity increment")
            if self.stop_price >= self.entry_price:
                raise ValueError("long stop must remain below entry")
            if self.unit_risk != self.entry_price - self.stop_price:
                raise ValueError("unit risk must equal entry minus stop")
            if self.unit_modeled_loss != (
                self.unit_risk + self.entry_price * self.round_trip_cost_return
            ):
                raise ValueError("unit modeled loss is arithmetically inconsistent")
            if self.cash_per_unit != (
                self.entry_price * (Decimal(1) + self.round_trip_cost_return)
            ):
                raise ValueError("cash per unit is arithmetically inconsistent")
            if self.modeled_risk_amount != self.quantity * self.unit_modeled_loss:
                raise ValueError("modeled risk amount is arithmetically inconsistent")
            if self.reservation_amount != self.quantity * self.cash_per_unit:
                raise ValueError("reservation amount is arithmetically inconsistent")
            if self.modeled_risk_amount > self.allowed_risk_amount:
                raise ValueError("modeled risk exceeds allowed risk")
            if self.quantity > derived.raw_quantity:
                raise ValueError("quantity exceeds deterministic capacity")
        if self.sizing_decision_id != calculate_sizing_decision_id(self):
            raise ValueError("sizing decision identity does not match content")
        return self


def calculate_sizing_decision_id(
    decision: SizingDecision | dict[str, object],
) -> SizingDecisionId:
    return SizingDecisionId.parse(
        sha256_content_id(_content_without_id(decision, "sizing_decision_id"))
    )


class RiskDecisionStatus(StrEnum):
    APPROVED_FOR_RESERVATION = "APPROVED_FOR_RESERVATION"
    REJECTED = "REJECTED"


class RiskRejectionCode(StrEnum):
    INSUFFICIENT_AVAILABLE_CAPITAL = "INSUFFICIENT_AVAILABLE_CAPITAL"
    INVALID_PROPOSAL = "INVALID_PROPOSAL"
    MISSING_PROTECTIVE_STOP = "MISSING_PROTECTIVE_STOP"
    INVALID_STOP_GEOMETRY = "INVALID_STOP_GEOMETRY"
    RISK_PER_TRADE_EXCEEDED = "RISK_PER_TRADE_EXCEEDED"
    POSITION_SIZE_EXCEEDED = "POSITION_SIZE_EXCEEDED"
    AGENT_EXPOSURE_EXCEEDED = "AGENT_EXPOSURE_EXCEEDED"
    PARENT_EXPOSURE_EXCEEDED = "PARENT_EXPOSURE_EXCEEDED"
    INSTRUMENT_CONCENTRATION_EXCEEDED = "INSTRUMENT_CONCENTRATION_EXCEEDED"
    DRAWDOWN_LOCK = "DRAWDOWN_LOCK"
    TRADING_LOCK = "TRADING_LOCK"
    STALE_PROPOSAL = "STALE_PROPOSAL"
    EXPIRED_PROPOSAL = "EXPIRED_PROPOSAL"
    FUTURE_PROPOSAL = "FUTURE_PROPOSAL"
    UNSUPPORTED_DIRECTION = "UNSUPPORTED_DIRECTION"
    ENVIRONMENT_RESTRICTION = "ENVIRONMENT_RESTRICTION"
    APPROVAL_POLICY_MISMATCH = "APPROVAL_POLICY_MISMATCH"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_CONTEXT_MISMATCH = "APPROVAL_CONTEXT_MISMATCH"
    OWNERSHIP_MISMATCH = "OWNERSHIP_MISMATCH"
    RESERVATION_CAPACITY_UNAVAILABLE = "RESERVATION_CAPACITY_UNAVAILABLE"
    CONFIGURATION_MISMATCH = "CONFIGURATION_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    DUPLICATE_TERMINAL_RESERVATION = "DUPLICATE_TERMINAL_RESERVATION"
    PRELIMINARY_DECISION_MISMATCH = "PRELIMINARY_DECISION_MISMATCH"
    SUBMISSION_NOT_ENABLED = "SUBMISSION_NOT_ENABLED"
    SAFETY_STATE_MISMATCH = "SAFETY_STATE_MISMATCH"
    FUTURE_SAFETY_STATE = "FUTURE_SAFETY_STATE"
    STALE_SAFETY_STATE = "STALE_SAFETY_STATE"


class RiskEvaluatedLimits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    parent_revision: Annotated[int, Field(ge=0)]
    allocation_revision: Annotated[int, Field(ge=0)]
    parent_available_capital: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    allocation_available_capital: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    parent_committed_and_reserved: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    allocation_committed_and_reserved: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    active_reservation_count: Annotated[int, Field(ge=0)]
    agent_eligible_current_equity: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    parent_eligible_current_equity: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    agent_daily_loss_ceiling: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    parent_daily_loss_ceiling: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    agent_current_loss: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    parent_current_loss: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    agent_outstanding_downside: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    parent_outstanding_downside: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    agent_remaining_loss_headroom: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    parent_remaining_loss_headroom: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]

    @model_validator(mode="before")
    @classmethod
    def reject_float_values(cls, data: object) -> object:
        if isinstance(data, dict) and any(
            isinstance(data.get(field), float)
            for field in cls.model_fields
            if field not in {"parent_revision", "allocation_revision", "active_reservation_count"}
        ):
            raise ValueError("evaluated financial limits must not use float")
        return data


def _derive_evaluated_limits(
    configuration: RiskConfiguration,
    state: RiskEvaluationState,
) -> RiskEvaluatedLimits:
    agent_ceiling, parent_ceiling, agent_remaining, parent_remaining = _loss_capacity(
        configuration, state
    )
    return RiskEvaluatedLimits(
        parent_revision=state.parent.revision,
        allocation_revision=state.allocation.revision,
        parent_available_capital=state.parent.available_capital,
        allocation_available_capital=state.allocation.available_capital,
        parent_committed_and_reserved=(
            state.parent.committed_capital + state.parent.active_reserved_capital
        ),
        allocation_committed_and_reserved=(
            state.allocation.committed_capital + state.allocation.active_reserved_capital
        ),
        active_reservation_count=state.allocation.active_reservation_count,
        agent_eligible_current_equity=state.safety.agent_loss_state.eligible_current_equity,
        parent_eligible_current_equity=state.safety.parent_loss_state.eligible_current_equity,
        agent_daily_loss_ceiling=agent_ceiling,
        parent_daily_loss_ceiling=parent_ceiling,
        agent_current_loss=state.safety.agent_loss_state.current_loss,
        parent_current_loss=state.safety.parent_loss_state.current_loss,
        agent_outstanding_downside=state.safety.agent_outstanding_downside,
        parent_outstanding_downside=state.safety.parent_outstanding_downside,
        agent_remaining_loss_headroom=agent_remaining,
        parent_remaining_loss_headroom=parent_remaining,
    )


class RiskDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    risk_decision_id: RiskDecisionId
    schema_version: Literal["risk-decision-v4"] = "risk-decision-v4"
    status: RiskDecisionStatus
    reason_codes: tuple[RiskRejectionCode, ...]
    proposal_id: TradeProposalId
    agent_id: AgentId
    account_id: AccountId
    allocation_id: AllocationId
    risk_configuration_id: RiskConfigurationId
    source_proposal: TradeProposal
    source_risk_configuration: RiskConfiguration
    source_evaluation_state: RiskEvaluationState
    evaluated_at: datetime
    evaluated_limits: RiskEvaluatedLimits
    evaluated_safety_state: SafetyStateSnapshot
    sizing_decision: SizingDecision | None = None

    @field_validator("evaluated_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        proposal = self.source_proposal
        configuration = self.source_risk_configuration
        state = self.source_evaluation_state
        ordered = tuple(sorted(set(self.reason_codes), key=lambda item: item.value))
        if ordered != self.reason_codes:
            raise ValueError("risk rejection codes must be unique and canonical")
        if self.status is RiskDecisionStatus.APPROVED_FOR_RESERVATION:
            if self.reason_codes or self.sizing_decision is None:
                raise ValueError("approved risk decision requires sizing and no rejection codes")
        elif not self.reason_codes or self.sizing_decision is not None:
            raise ValueError("rejected risk decision requires reasons and no sizing")
        if (
            proposal.proposal_id != self.proposal_id
            or configuration.risk_configuration_id != self.risk_configuration_id
            or state.parent.account_id != self.account_id
            or state.allocation.account_id != self.account_id
            or state.allocation.allocation_id != self.allocation_id
            or state.allocation.agent_id != self.agent_id
        ):
            raise ValueError("risk decision source attribution is inconsistent")
        if self.evaluated_safety_state != state.safety:
            raise ValueError("risk decision safety evidence differs from bound source state")
        if self.evaluated_limits != _derive_evaluated_limits(configuration, state):
            raise ValueError("evaluated limits are not derived from bound source state")
        if self.sizing_decision is not None and (
            self.sizing_decision.proposal_id != self.proposal_id
            or self.sizing_decision.agent_id != self.agent_id
            or self.sizing_decision.account_id != self.account_id
            or self.sizing_decision.allocation_id != self.allocation_id
            or self.sizing_decision.risk_configuration_id != self.risk_configuration_id
            or self.sizing_decision.source_proposal != proposal
            or self.sizing_decision.source_risk_configuration != configuration
            or self.sizing_decision.source_evaluation_state != state
        ):
            raise ValueError("sizing decision attribution differs from risk decision")
        limits = self.evaluated_limits
        safety = self.evaluated_safety_state
        if (
            limits.agent_eligible_current_equity != safety.agent_loss_state.eligible_current_equity
            or limits.parent_eligible_current_equity
            != safety.parent_loss_state.eligible_current_equity
            or limits.agent_current_loss != safety.agent_loss_state.current_loss
            or limits.parent_current_loss != safety.parent_loss_state.current_loss
            or limits.agent_outstanding_downside != safety.agent_outstanding_downside
            or limits.parent_outstanding_downside != safety.parent_outstanding_downside
        ):
            raise ValueError("evaluated limits do not match bound safety state")
        with localcontext(_DECIMAL_CONTEXT):
            if limits.agent_remaining_loss_headroom != max(
                Decimal(0),
                limits.agent_daily_loss_ceiling
                - limits.agent_current_loss
                - limits.agent_outstanding_downside,
            ) or limits.parent_remaining_loss_headroom != max(
                Decimal(0),
                limits.parent_daily_loss_ceiling
                - limits.parent_current_loss
                - limits.parent_outstanding_downside,
            ):
                raise ValueError("remaining loss headroom is arithmetically inconsistent")
        if self.sizing_decision is not None and (
            self.sizing_decision.allowed_risk_amount
            > min(
                limits.agent_remaining_loss_headroom,
                limits.parent_remaining_loss_headroom,
            )
        ):
            raise ValueError("sizing exceeds bound remaining loss headroom")
        if self.sizing_decision is not None:
            configuration = self.sizing_decision.source_risk_configuration
            with localcontext(_DECIMAL_CONTEXT):
                expected_agent_ceiling = configuration.max_agent_drawdown_fraction * min(
                    safety.agent_loss_state.session_start_equity,
                    safety.agent_loss_state.eligible_current_equity,
                )
                expected_parent_ceiling = configuration.max_parent_drawdown_fraction * min(
                    safety.parent_loss_state.session_start_equity,
                    safety.parent_loss_state.eligible_current_equity,
                )
                expected_allowed_risk = (
                    safety.agent_loss_state.eligible_current_equity
                    * configuration.max_risk_fraction
                )
                if configuration.max_monetary_risk is not None:
                    expected_allowed_risk = min(
                        expected_allowed_risk, configuration.max_monetary_risk
                    )
                expected_allowed_risk = min(
                    expected_allowed_risk,
                    limits.agent_remaining_loss_headroom,
                    limits.parent_remaining_loss_headroom,
                )
            if (
                limits.agent_daily_loss_ceiling != expected_agent_ceiling
                or limits.parent_daily_loss_ceiling != expected_parent_ceiling
            ):
                raise ValueError(
                    "evaluated loss ceilings do not match immutable risk configuration"
                )
            if self.sizing_decision.allowed_risk_amount != expected_allowed_risk:
                raise ValueError("allowed risk does not match immutable inputs")
        expected_safety_reasons: set[RiskRejectionCode] = set()
        loss_states = (safety.agent_loss_state, safety.parent_loss_state)
        if any(
            proposal.as_of < loss_state.session_start_at
            or proposal.as_of >= loss_state.session_end_at
            for loss_state in loss_states
        ):
            expected_safety_reasons.add(RiskRejectionCode.SAFETY_STATE_MISMATCH)
        if any(
            loss_state.effective_at > self.evaluated_at
            or loss_state.observed_at > self.evaluated_at
            for loss_state in loss_states
        ):
            expected_safety_reasons.add(RiskRejectionCode.FUTURE_SAFETY_STATE)
        if any(self.evaluated_at >= loss_state.valid_until for loss_state in loss_states):
            expected_safety_reasons.add(RiskRejectionCode.STALE_SAFETY_STATE)
        if any(
            lock.reason is SafetyLockReason.DRAWDOWN_LOCK for lock in safety.active_locks
        ) or any(loss_state.loss_breached for loss_state in loss_states):
            expected_safety_reasons.add(RiskRejectionCode.DRAWDOWN_LOCK)
        if any(lock.reason is not SafetyLockReason.DRAWDOWN_LOCK for lock in safety.active_locks):
            expected_safety_reasons.add(RiskRejectionCode.TRADING_LOCK)
        if limits.agent_remaining_loss_headroom <= 0 or limits.parent_remaining_loss_headroom <= 0:
            expected_safety_reasons.add(RiskRejectionCode.DRAWDOWN_LOCK)
        actual_safety_reasons = set(self.reason_codes).intersection(
            {
                RiskRejectionCode.SAFETY_STATE_MISMATCH,
                RiskRejectionCode.FUTURE_SAFETY_STATE,
                RiskRejectionCode.STALE_SAFETY_STATE,
                RiskRejectionCode.DRAWDOWN_LOCK,
                RiskRejectionCode.TRADING_LOCK,
            }
        )
        if actual_safety_reasons != expected_safety_reasons:
            raise ValueError("safety rejection reasons do not match bound causal evidence")
        expected_scope_reasons: set[RiskRejectionCode] = set()
        if proposal.agent_id != state.allocation.agent_id:
            expected_scope_reasons.add(RiskRejectionCode.OWNERSHIP_MISMATCH)
        if (
            proposal.authority_context.configuration_version_id
            != configuration.authority_configuration_version_id
            or state.allocation.configuration_version_id
            != configuration.authority_configuration_version_id
        ):
            expected_scope_reasons.add(RiskRejectionCode.CONFIGURATION_MISMATCH)
        if (
            proposal.entry.currency != state.parent.currency
            or proposal.entry.currency != state.allocation.currency
        ):
            expected_scope_reasons.add(RiskRejectionCode.CURRENCY_MISMATCH)
        actual_scope_reasons = set(self.reason_codes).intersection(
            {
                RiskRejectionCode.OWNERSHIP_MISMATCH,
                RiskRejectionCode.CONFIGURATION_MISMATCH,
                RiskRejectionCode.CURRENCY_MISMATCH,
            }
        )
        if actual_scope_reasons != expected_scope_reasons:
            raise ValueError("scope rejection reasons do not match bound source evidence")
        expected_context_reasons: set[RiskRejectionCode] = set()
        dimensions = proposal.authority_context.execution_dimensions
        if proposal.side is not ProposalSide.LONG:
            expected_context_reasons.add(RiskRejectionCode.UNSUPPORTED_DIRECTION)
        if proposal.stop_level >= proposal.entry.reference_price:
            expected_context_reasons.add(RiskRejectionCode.INVALID_STOP_GEOMETRY)
        if dimensions.execution_environment not in configuration.allowed_execution_environments:
            expected_context_reasons.add(RiskRejectionCode.ENVIRONMENT_RESTRICTION)
        if self.evaluated_at < proposal.as_of:
            expected_context_reasons.add(RiskRejectionCode.FUTURE_PROPOSAL)
        if self.evaluated_at >= proposal.valid_until:
            expected_context_reasons.add(RiskRejectionCode.EXPIRED_PROPOSAL)
        elif self.evaluated_at - proposal.as_of > timedelta(
            seconds=configuration.max_proposal_age_seconds
        ):
            expected_context_reasons.add(RiskRejectionCode.STALE_PROPOSAL)
        if state.allocation.active_reservation_count >= configuration.max_concurrent_reservations:
            expected_context_reasons.add(RiskRejectionCode.RESERVATION_CAPACITY_UNAVAILABLE)
        actual_context_reasons = set(self.reason_codes).intersection(
            {
                RiskRejectionCode.UNSUPPORTED_DIRECTION,
                RiskRejectionCode.INVALID_STOP_GEOMETRY,
                RiskRejectionCode.ENVIRONMENT_RESTRICTION,
                RiskRejectionCode.FUTURE_PROPOSAL,
                RiskRejectionCode.EXPIRED_PROPOSAL,
                RiskRejectionCode.STALE_PROPOSAL,
                RiskRejectionCode.RESERVATION_CAPACITY_UNAVAILABLE,
            }
        )
        if actual_context_reasons != expected_context_reasons:
            raise ValueError("context rejection reasons do not match bound source evidence")
        if (
            self.status is RiskDecisionStatus.APPROVED_FOR_RESERVATION
            and dimensions.approval_policy not in configuration.allowed_approval_policies
        ):
            raise ValueError("approved decision uses a disallowed approval policy")
        if self.risk_decision_id != calculate_risk_decision_id(self):
            raise ValueError("risk decision identity does not match content")
        return self


def calculate_risk_decision_id(decision: RiskDecision | dict[str, object]) -> RiskDecisionId:
    return RiskDecisionId.parse(
        sha256_content_id(_content_without_id(decision, "risk_decision_id"))
    )


class ApprovalBinding(BaseModel):
    """Future approval evidence; Phase 5 validates but never creates approval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approval_binding_id: ApprovalBindingId
    schema_version: Literal["approval-binding-v1"] = "approval-binding-v1"
    proposal_id: TradeProposalId
    sizing_decision_id: SizingDecisionId
    approved_quantity: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    management_mandate_id: ManagementMandateId
    configuration_version_id: ConfigurationVersionId
    execution_dimensions: ExecutionDimensions
    approved_at: datetime
    valid_until: datetime

    @field_validator("approved_quantity", mode="before")
    @classmethod
    def reject_float_quantity(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("approved quantity must not use float")
        return value

    @field_validator("approved_at", "valid_until")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        if self.valid_until <= self.approved_at:
            raise ValueError("approval binding validity must end after approval")
        if self.approval_binding_id != calculate_approval_binding_id(self):
            raise ValueError("approval binding identity does not match content")
        return self


def calculate_approval_binding_id(
    binding: ApprovalBinding | dict[str, object],
) -> ApprovalBindingId:
    return ApprovalBindingId.parse(
        sha256_content_id(_content_without_id(binding, "approval_binding_id"))
    )


class ReservationState(StrEnum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"


class CapitalReservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reservation_id: ReservationId
    schema_version: Literal["capital-reservation-v2"] = "capital-reservation-v2"
    proposal_id: TradeProposalId
    risk_decision_id: RiskDecisionId
    sizing_decision_id: SizingDecisionId
    risk_configuration_id: RiskConfigurationId
    account_id: AccountId
    allocation_id: AllocationId
    agent_id: AgentId
    instrument_id: InstrumentId
    reserved_amount: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    reserved_downside: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    approved_quantity: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    authority_context: ExecutionDimensions
    approval_binding_id: ApprovalBindingId | None = None
    created_at: datetime
    expires_at: datetime
    state: ReservationState = ReservationState.ACTIVE
    transitioned_at: datetime

    @field_validator("reserved_amount", "reserved_downside", "approved_quantity", mode="before")
    @classmethod
    def reject_float_values(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("reservation financial values must not use float")
        return value

    @field_validator("created_at", "expires_at", "transitioned_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_reservation(self) -> Self:
        if self.expires_at <= self.created_at:
            raise ValueError("reservation expiry must follow creation")
        if self.transitioned_at < self.created_at:
            raise ValueError("reservation transition cannot predate creation")
        if self.state is ReservationState.ACTIVE and self.transitioned_at != self.created_at:
            raise ValueError("active reservation transition time must equal creation time")
        if self.reservation_id != calculate_reservation_id(self):
            raise ValueError("reservation identity does not match immutable contract")
        return self


def _reservation_identity_content(
    reservation: CapitalReservation | dict[str, object],
) -> dict[str, object]:
    if isinstance(reservation, BaseModel):
        content = reservation.model_dump(mode="python")
    else:
        content = dict(reservation)
    for field in ("reservation_id", "state", "transitioned_at"):
        content.pop(field, None)
    return content


def calculate_reservation_id(
    reservation: CapitalReservation | dict[str, object],
) -> ReservationId:
    return ReservationId.parse(sha256_content_id(_reservation_identity_content(reservation)))


class ReservationAttemptStatus(StrEnum):
    RESERVED = "RESERVED"
    REJECTED = "REJECTED"


class ReservationAttempt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ReservationAttemptStatus
    risk_decision: RiskDecision
    reservation: CapitalReservation | None = None
    idempotent_replay: bool = False

    @model_validator(mode="after")
    def validate_attempt(self) -> Self:
        if self.status is ReservationAttemptStatus.RESERVED:
            if self.reservation is None:
                raise ValueError("reserved attempt requires reservation")
            if (
                self.risk_decision.status is not RiskDecisionStatus.APPROVED_FOR_RESERVATION
                or self.reservation.risk_decision_id != self.risk_decision.risk_decision_id
                or self.reservation.proposal_id != self.risk_decision.proposal_id
                or self.reservation.account_id != self.risk_decision.account_id
                or self.reservation.allocation_id != self.risk_decision.allocation_id
                or self.reservation.agent_id != self.risk_decision.agent_id
                or self.reservation.risk_configuration_id
                != self.risk_decision.risk_configuration_id
                or self.risk_decision.sizing_decision is None
                or self.reservation.sizing_decision_id
                != self.risk_decision.sizing_decision.sizing_decision_id
            ):
                raise ValueError("reservation attempt evidence is not consistently bound")
        elif self.reservation is not None:
            raise ValueError("rejected attempt cannot carry reservation")
        elif self.idempotent_replay:
            raise ValueError("rejected attempt cannot be an idempotent reservation replay")
        return self


class ReservationTransitionError(RuntimeError):
    """Raised for an ownership mismatch or conflicting terminal transition."""
