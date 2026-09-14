"""Pure deterministic Phase 5 risk evaluation and Decimal sizing."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import ROUND_FLOOR, Context, Decimal, localcontext

from ai_trading_scanner.domain.execution import ApprovalPolicy, SubmissionMode
from ai_trading_scanner.risk.models import (
    ApprovalBinding,
    RiskConfiguration,
    RiskDecision,
    RiskDecisionStatus,
    RiskEvaluatedLimits,
    RiskEvaluationState,
    RiskRejectionCode,
    SafetyLockReason,
    SizingDecision,
    calculate_risk_decision_id,
    calculate_sizing_decision_id,
)
from ai_trading_scanner.strategies import ProposalSide, SizingMethod, TradeProposal

_DECIMAL_CONTEXT = Context(prec=34)


def _canonical_reasons(reasons: set[RiskRejectionCode]) -> tuple[RiskRejectionCode, ...]:
    return tuple(sorted(reasons, key=lambda item: item.value))


def _floor_to_increment(value: Decimal, increment: Decimal) -> Decimal:
    with localcontext(_DECIMAL_CONTEXT):
        units = (value / increment).to_integral_value(rounding=ROUND_FLOOR)
        return units * increment


class RiskEngine:
    """Evaluate immutable proposals without I/O or state mutation."""

    def evaluate(
        self,
        proposal: TradeProposal,
        configuration: RiskConfiguration,
        state: RiskEvaluationState,
        *,
        evaluated_at: datetime,
    ) -> RiskDecision:
        """Run risk preflight; human approval is intentionally outside this step."""
        reasons = self._base_reasons(proposal, configuration, state, evaluated_at)
        sizing: SizingDecision | None = None
        if not reasons:
            sizing, sizing_reasons = self._size(proposal, configuration, state)
            reasons.update(sizing_reasons)
        if reasons:
            return self.rejection(
                proposal,
                configuration,
                state,
                evaluated_at=evaluated_at,
                reasons=reasons,
            )
        assert sizing is not None
        return self._decision(
            proposal,
            configuration,
            state,
            evaluated_at=evaluated_at,
            status=RiskDecisionStatus.APPROVED_FOR_RESERVATION,
            reasons=(),
            sizing=sizing,
        )

    def evaluate_for_reservation(
        self,
        proposal: TradeProposal,
        configuration: RiskConfiguration,
        state: RiskEvaluationState,
        *,
        evaluated_at: datetime,
        approval_binding: ApprovalBinding | None,
    ) -> RiskDecision:
        """Re-run risk and validate reservation authority against fresh state."""
        decision = self.evaluate(
            proposal,
            configuration,
            state,
            evaluated_at=evaluated_at,
        )
        if decision.status is RiskDecisionStatus.REJECTED:
            return decision

        reasons: set[RiskRejectionCode] = set()
        dimensions = proposal.authority_context.execution_dimensions
        if dimensions.submission_mode is not SubmissionMode.ORDER_ENABLED:
            reasons.add(RiskRejectionCode.SUBMISSION_NOT_ENABLED)
        if dimensions.approval_policy is ApprovalPolicy.MANUAL_APPROVAL:
            if proposal.sizing.method is not SizingMethod.FINAL_QUANTITY:
                reasons.add(RiskRejectionCode.APPROVAL_CONTEXT_MISMATCH)
            elif approval_binding is None:
                reasons.add(RiskRejectionCode.APPROVAL_REQUIRED)
            else:
                reasons.update(
                    self._approval_reasons(
                        proposal,
                        decision.sizing_decision,
                        approval_binding,
                        evaluated_at,
                    )
                )
        elif approval_binding is not None:
            reasons.add(RiskRejectionCode.APPROVAL_POLICY_MISMATCH)
        if reasons:
            return self.rejection(
                proposal,
                configuration,
                state,
                evaluated_at=evaluated_at,
                reasons=reasons,
            )
        return decision

    def rejection(
        self,
        proposal: TradeProposal,
        configuration: RiskConfiguration,
        state: RiskEvaluationState,
        *,
        evaluated_at: datetime,
        reasons: set[RiskRejectionCode],
    ) -> RiskDecision:
        return self._decision(
            proposal,
            configuration,
            state,
            evaluated_at=evaluated_at,
            status=RiskDecisionStatus.REJECTED,
            reasons=_canonical_reasons(reasons),
            sizing=None,
        )

    def _base_reasons(
        self,
        proposal: TradeProposal,
        configuration: RiskConfiguration,
        state: RiskEvaluationState,
        evaluated_at: datetime,
    ) -> set[RiskRejectionCode]:
        reasons: set[RiskRejectionCode] = set()
        if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
            raise ValueError("evaluation time must be timezone-aware")
        allocation = state.allocation
        parent = state.parent
        dimensions = proposal.authority_context.execution_dimensions

        if proposal.agent_id != allocation.agent_id:
            reasons.add(RiskRejectionCode.OWNERSHIP_MISMATCH)
        if allocation.account_id != parent.account_id:
            reasons.add(RiskRejectionCode.OWNERSHIP_MISMATCH)
        if (
            allocation.configuration_version_id != configuration.authority_configuration_version_id
            or proposal.authority_context.configuration_version_id
            != configuration.authority_configuration_version_id
        ):
            reasons.add(RiskRejectionCode.CONFIGURATION_MISMATCH)
        if proposal.entry.currency != allocation.currency or allocation.currency != parent.currency:
            reasons.add(RiskRejectionCode.CURRENCY_MISMATCH)
        if proposal.side is not ProposalSide.LONG:
            reasons.add(RiskRejectionCode.UNSUPPORTED_DIRECTION)
        if proposal.stop_level >= proposal.entry.reference_price:
            reasons.add(RiskRejectionCode.INVALID_STOP_GEOMETRY)
        if dimensions.execution_environment not in configuration.allowed_execution_environments:
            reasons.add(RiskRejectionCode.ENVIRONMENT_RESTRICTION)
        if dimensions.approval_policy not in configuration.allowed_approval_policies:
            reasons.add(RiskRejectionCode.APPROVAL_POLICY_MISMATCH)
        if evaluated_at < proposal.as_of:
            reasons.add(RiskRejectionCode.FUTURE_PROPOSAL)
        if evaluated_at >= proposal.valid_until:
            reasons.add(RiskRejectionCode.EXPIRED_PROPOSAL)
        elif evaluated_at - proposal.as_of > timedelta(
            seconds=configuration.max_proposal_age_seconds
        ):
            reasons.add(RiskRejectionCode.STALE_PROPOSAL)
        if state.safety.active_locks:
            if any(
                lock.reason is SafetyLockReason.DRAWDOWN_LOCK for lock in state.safety.active_locks
            ):
                reasons.add(RiskRejectionCode.DRAWDOWN_LOCK)
            if any(
                lock.reason is not SafetyLockReason.DRAWDOWN_LOCK
                for lock in state.safety.active_locks
            ):
                reasons.add(RiskRejectionCode.TRADING_LOCK)
        if (
            state.safety.agent_loss_breached
            or state.safety.parent_loss_breached
            or state.safety.agent_drawdown_fraction >= configuration.max_agent_drawdown_fraction
            or state.safety.parent_drawdown_fraction >= configuration.max_parent_drawdown_fraction
        ):
            reasons.add(RiskRejectionCode.DRAWDOWN_LOCK)
        if allocation.active_reservation_count >= configuration.max_concurrent_reservations:
            reasons.add(RiskRejectionCode.RESERVATION_CAPACITY_UNAVAILABLE)
        return reasons

    def _size(
        self,
        proposal: TradeProposal,
        configuration: RiskConfiguration,
        state: RiskEvaluationState,
    ) -> tuple[SizingDecision | None, set[RiskRejectionCode]]:
        reasons: set[RiskRejectionCode] = set()
        allocation = state.allocation
        parent = state.parent
        entry = proposal.entry.reference_price
        stop = proposal.stop_level
        with localcontext(_DECIMAL_CONTEXT):
            unit_risk = entry - stop
            if unit_risk <= 0:
                return None, {RiskRejectionCode.INVALID_STOP_GEOMETRY}
            cost_return = proposal.economics.cost_estimate.total_return_drag
            unit_modeled_loss = unit_risk + entry * cost_return
            risk_budget = allocation.allocated_capital * configuration.max_risk_fraction
            if configuration.max_monetary_risk is not None:
                risk_budget = min(risk_budget, configuration.max_monetary_risk)

            cash_per_unit = entry * (Decimal(1) + cost_return)
            position_headroom = allocation.allocated_capital * (configuration.max_position_fraction)
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
            candidates = (
                risk_budget / unit_modeled_loss,
                available / cash_per_unit,
                position_headroom / cash_per_unit,
                max(agent_headroom, Decimal(0)) / cash_per_unit,
                max(parent_headroom, Decimal(0)) / cash_per_unit,
                max(instrument_headroom, Decimal(0)) / cash_per_unit,
            )
            raw_quantity = min(candidates)
            final_quantity = proposal.sizing.final_quantity
            if proposal.sizing.method is SizingMethod.FINAL_QUANTITY:
                assert final_quantity is not None
                if final_quantity % configuration.quantity_increment != 0:
                    return None, {RiskRejectionCode.INVALID_PROPOSAL}
                if final_quantity > raw_quantity:
                    if available < final_quantity * cash_per_unit:
                        reasons.add(RiskRejectionCode.INSUFFICIENT_AVAILABLE_CAPITAL)
                    if risk_budget < final_quantity * unit_modeled_loss:
                        reasons.add(RiskRejectionCode.RISK_PER_TRADE_EXCEEDED)
                    if position_headroom < final_quantity * cash_per_unit:
                        reasons.add(RiskRejectionCode.POSITION_SIZE_EXCEEDED)
                    if agent_headroom < final_quantity * cash_per_unit:
                        reasons.add(RiskRejectionCode.AGENT_EXPOSURE_EXCEEDED)
                    if parent_headroom < final_quantity * cash_per_unit:
                        reasons.add(RiskRejectionCode.PARENT_EXPOSURE_EXCEEDED)
                    if instrument_headroom < final_quantity * cash_per_unit:
                        reasons.add(RiskRejectionCode.INSTRUMENT_CONCENTRATION_EXCEEDED)
                    return None, reasons or {RiskRejectionCode.INVALID_PROPOSAL}
                quantity = final_quantity
            else:
                quantity = _floor_to_increment(raw_quantity, configuration.quantity_increment)

            if quantity <= 0:
                if available < cash_per_unit * configuration.quantity_increment:
                    reasons.add(RiskRejectionCode.INSUFFICIENT_AVAILABLE_CAPITAL)
                if risk_budget < unit_modeled_loss * configuration.quantity_increment:
                    reasons.add(RiskRejectionCode.RISK_PER_TRADE_EXCEEDED)
                if position_headroom < cash_per_unit * configuration.quantity_increment:
                    reasons.add(RiskRejectionCode.POSITION_SIZE_EXCEEDED)
                if agent_headroom < cash_per_unit * configuration.quantity_increment:
                    reasons.add(RiskRejectionCode.AGENT_EXPOSURE_EXCEEDED)
                if parent_headroom < cash_per_unit * configuration.quantity_increment:
                    reasons.add(RiskRejectionCode.PARENT_EXPOSURE_EXCEEDED)
                if instrument_headroom < cash_per_unit * configuration.quantity_increment:
                    reasons.add(RiskRejectionCode.INSTRUMENT_CONCENTRATION_EXCEEDED)
                if not reasons:
                    reasons.add(RiskRejectionCode.INSUFFICIENT_AVAILABLE_CAPITAL)
                return None, reasons

            modeled_risk = quantity * unit_modeled_loss
            reservation_amount = quantity * cash_per_unit
            content: dict[str, object] = {
                "schema_version": "sizing-decision-v1",
                "proposal_id": proposal.proposal_id,
                "risk_configuration_id": configuration.risk_configuration_id,
                "account_id": parent.account_id,
                "allocation_id": allocation.allocation_id,
                "agent_id": allocation.agent_id,
                "quantity": quantity,
                "quantity_increment": configuration.quantity_increment,
                "entry_price": entry,
                "stop_price": stop,
                "unit_risk": unit_risk,
                "unit_modeled_loss": unit_modeled_loss,
                "allowed_risk_amount": risk_budget,
                "modeled_risk_amount": modeled_risk,
                "reservation_amount": reservation_amount,
                "currency": allocation.currency,
            }
            sizing = SizingDecision(
                sizing_decision_id=calculate_sizing_decision_id(content),
                **content,  # type: ignore[arg-type]
            )
            return sizing, reasons

    def _approval_reasons(
        self,
        proposal: TradeProposal,
        sizing: SizingDecision | None,
        binding: ApprovalBinding,
        evaluated_at: datetime,
    ) -> set[RiskRejectionCode]:
        if sizing is None:
            return {RiskRejectionCode.APPROVAL_CONTEXT_MISMATCH}
        if (
            binding.approved_at < proposal.generated_at
            or evaluated_at < binding.approved_at
            or evaluated_at >= binding.valid_until
            or binding.valid_until > proposal.valid_until
        ):
            return {RiskRejectionCode.APPROVAL_CONTEXT_MISMATCH}
        if (
            binding.proposal_id != proposal.proposal_id
            or binding.sizing_decision_id != sizing.sizing_decision_id
            or binding.approved_quantity != sizing.quantity
            or binding.management_mandate_id != proposal.management_mandate.mandate_id
            or binding.configuration_version_id
            != proposal.authority_context.configuration_version_id
            or binding.execution_dimensions != proposal.authority_context.execution_dimensions
        ):
            return {RiskRejectionCode.APPROVAL_CONTEXT_MISMATCH}
        return set()

    def _decision(
        self,
        proposal: TradeProposal,
        configuration: RiskConfiguration,
        state: RiskEvaluationState,
        *,
        evaluated_at: datetime,
        status: RiskDecisionStatus,
        reasons: tuple[RiskRejectionCode, ...],
        sizing: SizingDecision | None,
    ) -> RiskDecision:
        limits = RiskEvaluatedLimits(
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
        )
        content: dict[str, object] = {
            "schema_version": "risk-decision-v1",
            "status": status,
            "reason_codes": reasons,
            "proposal_id": proposal.proposal_id,
            "agent_id": state.allocation.agent_id,
            "account_id": state.parent.account_id,
            "allocation_id": state.allocation.allocation_id,
            "risk_configuration_id": configuration.risk_configuration_id,
            "evaluated_at": evaluated_at,
            "evaluated_limits": limits,
            "sizing_decision": sizing,
        }
        return RiskDecision(
            risk_decision_id=calculate_risk_decision_id(content),
            **content,  # type: ignore[arg-type]
        )
