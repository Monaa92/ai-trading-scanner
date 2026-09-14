"""Mandatory cross-contract validation for one offline simulated fill chain."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, localcontext
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from ai_trading_scanner.domain.execution import ApprovalPolicy, ExecutionEnvironment
from ai_trading_scanner.market_data import CanonicalDataset, HistoricalBar
from ai_trading_scanner.risk import (
    ApprovalBinding,
    CapitalReservation,
    ReservationState,
    RiskDecision,
    RiskDecisionStatus,
)
from ai_trading_scanner.simulation.models import (
    SimulatedFill,
    SimulatedOrder,
    SimulatedOrderSide,
    SimulationExecutionConfiguration,
    SimulationRunManifest,
    TransactionCostConfiguration,
    calculate_fill_costs,
    validate_fill_against_order,
)
from ai_trading_scanner.simulation.portfolio import PositionChange, PositionChangeKind
from ai_trading_scanner.strategies import TradeProposalDecision


class ValidatedExecutionChain(BaseModel):
    """One fail-closed Phase 4→6 chain; it performs no I/O or execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest: SimulationRunManifest
    strategy_decision: TradeProposalDecision
    risk_decision: RiskDecision
    reservation: CapitalReservation
    approval_binding: ApprovalBinding | None = None
    execution_configuration: SimulationExecutionConfiguration
    cost_configuration: TransactionCostConfiguration
    order: SimulatedOrder
    dataset: CanonicalDataset
    fill: SimulatedFill
    position_change: PositionChange

    @model_validator(mode="after")
    def validate_chain(self) -> Self:
        proposal = self.strategy_decision.proposal
        sizing = self.risk_decision.sizing_decision
        dimensions = proposal.authority_context.execution_dimensions
        if (
            self.manifest.execution_dimensions.execution_environment
            is not ExecutionEnvironment.SIMULATION
        ):
            raise ValueError("validated execution chain requires SIMULATION")
        if (
            self.manifest.execution_dimensions != dimensions
            or self.reservation.authority_context != dimensions
        ):
            raise ValueError("execution dimensions differ across proposal, reservation, and run")
        if (
            self.manifest.dataset_id != proposal.dataset_id
            or self.manifest.dataset_id != self.dataset.dataset_id
            or self.manifest.agent_id != proposal.agent_id
            or self.manifest.strategy_id != proposal.strategy_id
            or self.manifest.strategy_configuration_id != proposal.strategy_configuration_id
            or self.manifest.strategy_version != proposal.strategy_version
            or self.manifest.management_mandate_id != proposal.management_mandate.mandate_id
            or self.manifest.configuration_version_id
            != proposal.authority_context.configuration_version_id
            or self.manifest.indicator_configuration_ids != proposal.indicator_configuration_ids
        ):
            raise ValueError("run manifest differs from immutable strategy proposal")
        if self.strategy_decision.decision_id != self.order.strategy_decision_id:
            raise ValueError("order does not reference the validated strategy decision")
        if (
            self.risk_decision.status is not RiskDecisionStatus.APPROVED_FOR_RESERVATION
            or sizing is None
            or self.risk_decision.source_proposal != proposal
            or self.risk_decision.risk_decision_id != self.order.risk_decision_id
            or self.manifest.risk_configuration_id != self.risk_decision.risk_configuration_id
        ):
            raise ValueError("order does not reference one approved bound risk decision")
        if (
            self.reservation.state is not ReservationState.ACTIVE
            or self.reservation.reservation_id != self.order.reservation_id
            or self.reservation.proposal_id != proposal.proposal_id
            or self.reservation.risk_decision_id != self.risk_decision.risk_decision_id
            or self.reservation.sizing_decision_id != sizing.sizing_decision_id
            or self.reservation.risk_configuration_id != self.risk_decision.risk_configuration_id
            or self.reservation.approved_quantity != sizing.quantity
        ):
            raise ValueError("active reservation does not match approved risk sizing")
        ownership = (
            self.manifest.account_id,
            self.manifest.allocation_id,
            self.manifest.agent_id,
        )
        for value in (self.risk_decision, self.reservation, self.order, self.fill):
            if (value.account_id, value.allocation_id, value.agent_id) != ownership:
                raise ValueError("execution-chain account, allocation, or agent differs")
        if dimensions.approval_policy is ApprovalPolicy.MANUAL_APPROVAL:
            self._validate_manual_approval(sizing.quantity)
        elif self.approval_binding is not None or self.reservation.approval_binding_id is not None:
            raise ValueError("FULL_AUTO chain cannot carry manual approval authority")
        if (
            self.execution_configuration.execution_model_id != self.manifest.execution_model_id
            or self.order.execution_model_id != self.manifest.execution_model_id
            or self.fill.execution_model_id != self.manifest.execution_model_id
        ):
            raise ValueError("execution model differs from frozen run manifest")
        if (
            self.cost_configuration.cost_model_id != self.manifest.cost_model_id
            or self.fill.costs.cost_model_id != self.manifest.cost_model_id
        ):
            raise ValueError("cost model differs from frozen run manifest")
        if (
            self.order.proposal_id != proposal.proposal_id
            or self.order.strategy_id != proposal.strategy_id
            or self.order.management_mandate_id != proposal.management_mandate.mandate_id
            or self.order.instrument_id != proposal.instrument_id
            or self.order.side is not SimulatedOrderSide.BUY
            or self.order.currency != proposal.entry.currency
            or self.order.quantity != sizing.quantity
            or self.order.quantity != self.reservation.approved_quantity
        ):
            raise ValueError("simulated order differs from approved immutable terms")
        with localcontext() as context:
            context.prec = 34
            if (
                self.order.quantity % self.execution_configuration.quantity_increment != 0
                or sizing.quantity_increment != self.execution_configuration.quantity_increment
            ):
                raise ValueError("order quantity does not align to the frozen increment")
        expected_eligible = self.order.submitted_at + timedelta(
            seconds=self.execution_configuration.routing_latency_seconds
        )
        if self.order.eligible_at != expected_eligible:
            raise ValueError("order eligibility does not equal submission plus configured latency")
        if (
            self.order.decision_at != proposal.as_of
            or self.order.submitted_at < self.risk_decision.evaluated_at
            or self.order.valid_until > proposal.valid_until
            or self.order.valid_until > self.reservation.expires_at
        ):
            raise ValueError("order causal or validity times exceed bound authority")
        validate_fill_against_order(self.fill, self.order)
        source_bar = self._validated_next_bar()
        if (
            self.fill.market_event.dataset_id != self.dataset.dataset_id
            or self.fill.market_event.instrument_id != source_bar.instrument_id
            or self.fill.market_event.interval_start_at != source_bar.start_at
            or self.fill.market_event.event_at != source_bar.end_at
            or self.fill.market_event.available_at != source_bar.available_at
            or self.fill.market_event.source_record_id != source_bar.source_record_id
            or self.fill.fill_price != source_bar.open
            or self.fill.currency != source_bar.currency
            or self.fill.fill_at != source_bar.available_at
        ):
            raise ValueError("fill does not use the canonical next eligible bar open")
        expected_costs = calculate_fill_costs(
            self.cost_configuration, self.fill.quantity, source_bar.open
        )
        if self.fill.costs != expected_costs:
            raise ValueError("fill costs differ from the frozen cost configuration")
        self._validate_position_change()
        return self

    def _validate_manual_approval(self, quantity: Decimal) -> None:
        approval = self.approval_binding
        sizing = self.risk_decision.sizing_decision
        assert sizing is not None
        if approval is None or self.reservation.approval_binding_id != approval.approval_binding_id:
            raise ValueError("manual approval chain requires its bound approval artifact")
        if (
            approval.proposal_id != self.order.proposal_id
            or approval.sizing_decision_id != sizing.sizing_decision_id
            or approval.approved_quantity != quantity
            or approval.management_mandate_id != self.order.management_mandate_id
            or approval.configuration_version_id != self.manifest.configuration_version_id
            or approval.execution_dimensions != self.manifest.execution_dimensions
            or self.order.submitted_at < approval.approved_at
            or self.order.valid_until > approval.valid_until
        ):
            raise ValueError("manual approval does not bind the submitted order terms")

    def _validated_next_bar(self) -> HistoricalBar:
        candidates = tuple(
            sorted(
                (
                    bar
                    for bar in self.dataset.bars
                    if bar.instrument_id == self.order.instrument_id
                    and bar.start_at > self.order.eligible_at
                    and bar.start_at < self.order.valid_until
                ),
                key=lambda bar: (bar.start_at, bar.end_at, bar.source_record_id or ""),
            )
        )
        if not candidates:
            raise ValueError("no eligible canonical execution bar exists before expiry")
        return candidates[0]

    def _validate_position_change(self) -> None:
        change = self.position_change
        if (
            change.run_id != self.manifest.run_id
            or change.account_id != self.manifest.account_id
            or change.allocation_id != self.manifest.allocation_id
            or change.agent_id != self.manifest.agent_id
            or change.proposal_id != self.order.proposal_id
            or change.order_id != self.order.order_id
            or change.fill_id != self.fill.fill_id
            or change.management_mandate_id != self.order.management_mandate_id
            or change.changed_at != self.fill.fill_at
        ):
            raise ValueError("portfolio change is not bound to the validated fill")
        if self.order.side is SimulatedOrderSide.BUY:
            if (
                change.kind is not PositionChangeKind.OPEN
                or change.quantity_delta != self.fill.quantity
            ):
                raise ValueError("V1 buy fill must open exactly its validated quantity")
        elif (
            change.kind not in {PositionChangeKind.DECREASE, PositionChangeKind.CLOSE}
            or change.quantity_delta != -self.fill.quantity
        ):
            raise ValueError("V1 sell fill must reduce exactly its validated quantity")


def validate_execution_chain(chain: ValidatedExecutionChain) -> None:
    """Explicit API used by the future scheduler before accepting a simulated fill."""
    if not isinstance(chain, ValidatedExecutionChain):
        raise TypeError("execution chain must be a validated contract")
