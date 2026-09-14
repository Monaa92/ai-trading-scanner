"""Small deterministic Phase 5 risk and allocation fixtures."""

from datetime import timedelta
from decimal import Decimal

from strategy_helpers import evaluation_context, strategy_bars

from ai_trading_scanner.domain import (
    AccountId,
    AgentId,
    AllocationId,
    ConfigurationVersionId,
)
from ai_trading_scanner.domain.execution import (
    ApprovalPolicy,
    ExecutionEnvironment,
    SubmissionMode,
)
from ai_trading_scanner.risk import (
    AllocationSnapshot,
    ApprovalBinding,
    InMemoryCapitalCoordinator,
    ParentCapitalSnapshot,
    RiskConfiguration,
    RiskEngine,
    RiskEvaluationState,
    SafetyStateSnapshot,
    baseline_risk_configuration,
    calculate_approval_binding_id,
    calculate_risk_configuration_id,
)
from ai_trading_scanner.strategies import (
    MomentumConfiguration,
    SizingIntent,
    SizingMethod,
    TradeProposal,
    TradeProposalDecision,
    calculate_trade_proposal_id,
    evaluate_strategy,
)

AUTHORITY_ID = ConfigurationVersionId.parse("phase4-fixture-v1")
ACCOUNT_ID = AccountId.parse("account:test")


def risk_policy(**overrides: object) -> RiskConfiguration:
    base = baseline_risk_configuration(AUTHORITY_ID)
    content = base.model_dump(mode="python", exclude={"risk_configuration_id"})
    content.update(
        {
            "max_risk_fraction": Decimal("1"),
            "max_position_fraction": Decimal("1"),
            "max_agent_exposure_fraction": Decimal("1"),
            "max_parent_exposure_fraction": Decimal("1"),
            "max_instrument_exposure_fraction": Decimal("1"),
            "max_concurrent_reservations": 2,
            "quantity_increment": Decimal("0.1"),
        }
    )
    content.update(overrides)
    return RiskConfiguration(
        risk_configuration_id=calculate_risk_configuration_id(content),
        **content,
    )


def trade_proposal(
    *,
    agent: str = "agent:A",
    environment: ExecutionEnvironment = ExecutionEnvironment.SIMULATION,
    submission_mode: SubmissionMode = SubmissionMode.ORDER_ENABLED,
    approval_policy: ApprovalPolicy = ApprovalPolicy.FULL_AUTO,
    final_quantity: Decimal | None = None,
    validity_extension_minutes: int = 0,
) -> TradeProposal:
    configuration = MomentumConfiguration()
    closes = ["100"] * 54 + ["101", "102", "101", "102", "103", "105"]
    highs = [str(Decimal(close) + Decimal("0.5")) for close in closes]
    highs[50] = "110"
    highs[-2] = "104"
    highs[-1] = "105.5"
    lows = ["99.5"] * 60
    lows[-4] = "100.5"
    decision = evaluate_strategy(
        evaluation_context(
            configuration,
            strategy_bars(closes, highs=highs, lows=lows),
            agent=agent,
        ),
        configuration,
    )
    assert isinstance(decision, TradeProposalDecision)
    original = decision.proposal
    dimensions = original.authority_context.execution_dimensions.model_copy(
        update={
            "execution_environment": environment,
            "submission_mode": submission_mode,
            "approval_policy": approval_policy,
        }
    )
    sizing = (
        original.sizing
        if final_quantity is None
        else SizingIntent(
            method=SizingMethod.FINAL_QUANTITY,
            final_quantity=final_quantity,
        )
    )
    content = original.model_dump(mode="python", exclude={"proposal_id"})
    content.update(
        {
            "sizing": sizing,
            "valid_until": original.valid_until + timedelta(minutes=validity_extension_minutes),
            "authority_context": original.authority_context.model_copy(
                update={"execution_dimensions": dimensions}
            ),
        }
    )
    return TradeProposal(
        proposal_id=calculate_trade_proposal_id(content),
        **content,
    )


def parent_snapshot(capital: str = "100") -> ParentCapitalSnapshot:
    amount = Decimal(capital)
    return ParentCapitalSnapshot(
        account_id=ACCOUNT_ID,
        currency="USD",
        total_capital=amount,
        available_capital=amount,
    )


def allocation_snapshot(
    *,
    agent: str = "agent:A",
    allocation: str = "allocation:A",
    capital: str = "100",
) -> AllocationSnapshot:
    amount = Decimal(capital)
    return AllocationSnapshot(
        allocation_id=AllocationId.parse(allocation),
        account_id=ACCOUNT_ID,
        agent_id=AgentId.parse(agent),
        configuration_version_id=AUTHORITY_ID,
        currency="USD",
        allocated_capital=amount,
        available_capital=amount,
    )


def state(
    *,
    parent: ParentCapitalSnapshot | None = None,
    allocation: AllocationSnapshot | None = None,
    safety: SafetyStateSnapshot | None = None,
) -> RiskEvaluationState:
    return RiskEvaluationState(
        parent=parent or parent_snapshot(),
        allocation=allocation or allocation_snapshot(),
        safety=safety or SafetyStateSnapshot(),
    )


def coordinator(
    *,
    parent: ParentCapitalSnapshot | None = None,
    allocations: tuple[AllocationSnapshot, ...] | None = None,
) -> InMemoryCapitalCoordinator:
    result = InMemoryCapitalCoordinator()
    result.register_parent(parent or parent_snapshot())
    for allocation in allocations or (allocation_snapshot(),):
        result.register_allocation(allocation)
    return result


def approval_binding(
    proposal: TradeProposal,
    state_snapshot: RiskEvaluationState,
    policy: RiskConfiguration,
) -> ApprovalBinding:
    decision = RiskEngine().evaluate(
        proposal,
        policy,
        state_snapshot,
        evaluated_at=proposal.as_of,
    )
    sizing = decision.sizing_decision
    assert sizing is not None
    content: dict[str, object] = {
        "schema_version": "approval-binding-v1",
        "proposal_id": proposal.proposal_id,
        "sizing_decision_id": sizing.sizing_decision_id,
        "approved_quantity": sizing.quantity,
        "management_mandate_id": proposal.management_mandate.mandate_id,
        "configuration_version_id": proposal.authority_context.configuration_version_id,
        "execution_dimensions": proposal.authority_context.execution_dimensions,
        "approved_at": proposal.as_of,
        "valid_until": proposal.valid_until,
    }
    return ApprovalBinding.model_validate(
        {
            "approval_binding_id": calculate_approval_binding_id(content),
            **content,
        }
    )
