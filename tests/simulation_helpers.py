from datetime import UTC, datetime
from decimal import Decimal

from ai_trading_scanner.domain import (
    AccountId,
    AgentId,
    AllocationId,
    ConfigurationVersionId,
    DatasetId,
    IndicatorConfigurationId,
    InstrumentId,
    ManagementMandateId,
    PortfolioSnapshotId,
    ReservationId,
    RiskConfigurationId,
    RiskDecisionId,
    StrategyConfigurationId,
    StrategyDecisionId,
    StrategyId,
    TradeProposalId,
)
from ai_trading_scanner.domain.execution import (
    ApprovalPolicy,
    DataRunMode,
    ExecutionDimensions,
    ExecutionEnvironment,
    OperatingContext,
    SubmissionMode,
)
from ai_trading_scanner.simulation import (
    CashLedgerSnapshot,
    MarketEventReference,
    PortfolioSnapshot,
    ReplayArtifactBundle,
    ReplayEvent,
    ReplayPayloadKind,
    ReplayPhase,
    ResultFinalizationPayload,
    SimulatedFill,
    SimulatedOrder,
    SimulatedOrderSide,
    SimulationExecutionConfiguration,
    SimulationResultStatus,
    SimulationRunManifest,
    TransactionCostConfiguration,
    calculate_cost_model_id,
    calculate_execution_model_id,
    calculate_fill_costs,
    calculate_marker_payload_id,
    calculate_market_event_id,
    calculate_portfolio_snapshot_id,
    calculate_replay_event_id,
    calculate_simulated_fill_id,
    calculate_simulated_order_id,
    calculate_simulation_run_id,
)

BASE = datetime(2024, 7, 2, 13, 31, 2, tzinfo=UTC)


def digest(char: str) -> str:
    return "sha256:" + char * 64


def execution_configuration(**changes: object) -> SimulationExecutionConfiguration:
    content: dict[str, object] = {
        "schema_version": "simulation-execution-v1",
        "model_version": "next-bar-open-v1",
        "fill_price_policy": "NEXT_ELIGIBLE_BAR_OPEN",
        "routing_latency_seconds": 1,
        "quantity_increment": "0.0001",
        "partial_fills_supported": False,
        "missing_data_policy": "EXPIRE_UNFILLED",
        "gap_policy": "USE_NEXT_ELIGIBLE_OPEN",
        "ambiguity_policy": "STOP_FIRST",
        "randomness_policy": "NONE",
    }
    content.update(changes)
    return SimulationExecutionConfiguration.model_validate(
        {"execution_model_id": calculate_execution_model_id(content), **content}
    )


def cost_configuration(**changes: object) -> TransactionCostConfiguration:
    content: dict[str, object] = {
        "schema_version": "transaction-cost-v1",
        "profile_name": "TEST_US_EQUITY",
        "profile_version": "v1",
        "currency": "USD",
        "minimum_commission_per_order": "0.35",
        "commission_per_share": "0.0035",
        "spread_bps": "2",
        "slippage_bps": "3",
        "other_fee_bps": "0.1",
    }
    content.update(changes)
    return TransactionCostConfiguration.model_validate(
        {"cost_model_id": calculate_cost_model_id(content), **content}
    )


def execution_dimensions(**changes: object) -> ExecutionDimensions:
    content: dict[str, object] = {
        "data_run_mode": DataRunMode.HISTORICAL_REPLAY,
        "execution_environment": ExecutionEnvironment.SIMULATION,
        "submission_mode": SubmissionMode.ORDER_ENABLED,
        "approval_policy": ApprovalPolicy.FULL_AUTO,
        "operating_context": OperatingContext.NORMAL,
    }
    content.update(changes)
    return ExecutionDimensions.model_validate(content)


def run_manifest(**changes: object) -> SimulationRunManifest:
    execution = execution_configuration()
    costs = cost_configuration()
    content: dict[str, object] = {
        "schema_version": "simulation-run-manifest-v1",
        "dataset_id": DatasetId.parse(digest("a")),
        "account_id": AccountId.parse("account:test"),
        "allocation_id": AllocationId.parse("allocation:test"),
        "agent_id": AgentId.parse("agent:test"),
        "strategy_id": StrategyId.parse("strategy:test"),
        "strategy_configuration_id": StrategyConfigurationId.parse(digest("b")),
        "strategy_version": "BASELINE_RESEARCH_V1",
        "model_id": None,
        "indicator_configuration_ids": (
            IndicatorConfigurationId.parse(digest("c")),
            IndicatorConfigurationId.parse(digest("d")),
        ),
        "risk_configuration_id": RiskConfigurationId.parse(digest("e")),
        "management_mandate_id": ManagementMandateId.parse(digest("f")),
        "configuration_version_id": ConfigurationVersionId.parse("authority:v1"),
        "execution_model_id": execution.execution_model_id,
        "cost_model_id": costs.cost_model_id,
        "starting_capital": "50",
        "reporting_currency": "USD",
        "execution_dimensions": execution_dimensions(),
        "random_seed": None,
    }
    content.update(changes)
    return SimulationRunManifest.model_validate(
        {"run_id": calculate_simulation_run_id(content), **content}
    )


def market_event(**changes: object) -> MarketEventReference:
    content: dict[str, object] = {
        "schema_version": "market-event-reference-v1",
        "dataset_id": DatasetId.parse(digest("a")),
        "instrument_id": InstrumentId.parse("XNYS:AAPL"),
        "interval_start_at": datetime(2024, 7, 2, 13, 32, tzinfo=UTC),
        "event_at": datetime(2024, 7, 2, 13, 33, tzinfo=UTC),
        "available_at": datetime(2024, 7, 2, 13, 33, 2, tzinfo=UTC),
        "source_record_id": "bar:2024-07-02T13:32:00Z",
    }
    content.update(changes)
    return MarketEventReference.model_validate(
        {"market_event_id": calculate_market_event_id(content), **content}
    )


def simulated_order(**changes: object) -> SimulatedOrder:
    manifest = run_manifest()
    content: dict[str, object] = {
        "schema_version": "simulated-order-v1",
        "run_id": manifest.run_id,
        "account_id": manifest.account_id,
        "allocation_id": manifest.allocation_id,
        "agent_id": manifest.agent_id,
        "strategy_id": manifest.strategy_id,
        "management_mandate_id": manifest.management_mandate_id,
        "proposal_id": TradeProposalId.parse(digest("1")),
        "strategy_decision_id": StrategyDecisionId.parse(digest("2")),
        "risk_decision_id": RiskDecisionId.parse(digest("3")),
        "reservation_id": ReservationId.parse(digest("4")),
        "instrument_id": InstrumentId.parse("XNYS:AAPL"),
        "side": SimulatedOrderSide.BUY,
        "order_type": "MARKET",
        "quantity": "1",
        "currency": "USD",
        "execution_model_id": manifest.execution_model_id,
        "decision_at": BASE,
        "submitted_at": datetime(2024, 7, 2, 13, 31, 3, tzinfo=UTC),
        "eligible_at": datetime(2024, 7, 2, 13, 31, 4, tzinfo=UTC),
        "valid_until": datetime(2024, 7, 2, 13, 40, tzinfo=UTC),
    }
    content.update(changes)
    return SimulatedOrder.model_validate(
        {"order_id": calculate_simulated_order_id(content), **content}
    )


def simulated_fill(**changes: object) -> SimulatedFill:
    order = simulated_order()
    price = Decimal("100")
    quantity = Decimal("1")
    costs = calculate_fill_costs(cost_configuration(), quantity, price)
    source = market_event()
    content: dict[str, object] = {
        "schema_version": "simulated-fill-v1",
        "run_id": order.run_id,
        "order_id": order.order_id,
        "account_id": order.account_id,
        "allocation_id": order.allocation_id,
        "agent_id": order.agent_id,
        "proposal_id": order.proposal_id,
        "risk_decision_id": order.risk_decision_id,
        "reservation_id": order.reservation_id,
        "instrument_id": order.instrument_id,
        "side": order.side,
        "quantity": quantity,
        "fill_price": price,
        "currency": order.currency,
        "execution_model_id": order.execution_model_id,
        "market_event": source,
        "submitted_at": order.submitted_at,
        "eligible_at": order.eligible_at,
        "execution_interval_start_at": source.interval_start_at,
        "execution_interval_end_at": source.event_at,
        "simulated_execution_at": source.interval_start_at,
        "fill_at": source.available_at,
        "costs": costs,
    }
    content.update(changes)
    return SimulatedFill.model_validate(
        {"fill_id": calculate_simulated_fill_id(content), **content}
    )


def initial_portfolio(**changes: object) -> PortfolioSnapshot:
    manifest = run_manifest()
    content: dict[str, object] = {
        "schema_version": "portfolio-snapshot-v1",
        "run_id": manifest.run_id,
        "account_id": manifest.account_id,
        "allocation_id": manifest.allocation_id,
        "agent_id": manifest.agent_id,
        "previous_snapshot_id": None,
        "as_of": BASE,
        "starting_capital": "50",
        "cash": CashLedgerSnapshot(
            currency="USD",
            available_cash=Decimal("50"),
            reserved_cash=Decimal("0"),
            committed_cash=Decimal("0"),
            total_cash=Decimal("50"),
        ),
        "positions": (),
        "realized_gross_pnl": "0",
        "unrealized_gross_pnl": "0",
        "total_execution_costs": "0",
        "gross_trading_pnl": "0",
        "net_trading_pnl": "0",
        "total_equity": "50",
    }
    content.update(changes)
    return PortfolioSnapshot.model_validate(
        {"portfolio_snapshot_id": calculate_portfolio_snapshot_id(content), **content}
    )


def replay_event(
    phase: ReplayPhase = ReplayPhase.MARKET_DATA_AVAILABLE,
    scheduled_at: datetime = BASE,
    **changes: object,
) -> ReplayEvent:
    default_payload = {
        ReplayPhase.EXECUTION_RESOLUTION: ReplayPayloadKind.EXECUTION_RESOLUTION,
        ReplayPhase.FILL: ReplayPayloadKind.SIMULATED_FILL,
        ReplayPhase.PORTFOLIO_UPDATE: ReplayPayloadKind.PORTFOLIO_SNAPSHOT,
        ReplayPhase.SESSION_CONTROL: ReplayPayloadKind.SESSION_CONTROL,
        ReplayPhase.MARKET_DATA_AVAILABLE: ReplayPayloadKind.MARKET_EVENT,
        ReplayPhase.INDICATOR_UPDATE: ReplayPayloadKind.INDICATOR_UPDATE,
        ReplayPhase.STRATEGY_EVALUATION: ReplayPayloadKind.STRATEGY_DECISION,
        ReplayPhase.RISK_EVALUATION: ReplayPayloadKind.RISK_DECISION,
        ReplayPhase.ORDER_SUBMISSION: ReplayPayloadKind.SIMULATED_ORDER,
        ReplayPhase.RESULT_FINALIZATION: ReplayPayloadKind.RUN_RESULT,
    }[phase]
    content: dict[str, object] = {
        "schema_version": "replay-event-v1",
        "run_id": run_manifest().run_id,
        "scheduled_at": scheduled_at,
        "phase": phase,
        "payload_kind": default_payload,
        "payload_id": digest("9"),
    }
    content.update(changes)
    content["payload_id"] = str(content["payload_id"])
    return ReplayEvent.model_validate(
        {"replay_event_id": calculate_replay_event_id(content), **content}
    )


def previous_snapshot_id() -> PortfolioSnapshotId:
    return PortfolioSnapshotId.parse(digest("8"))


def minimal_replay_artifact(
    *, status: SimulationResultStatus = SimulationResultStatus.COMPLETE
) -> ReplayArtifactBundle:
    manifest = run_manifest()
    portfolio = initial_portfolio()
    finalization_content: dict[str, object] = {
        "schema_version": "result-finalization-payload-v1",
        "run_id": manifest.run_id,
        "status": status,
        "final_portfolio_snapshot_id": portfolio.portfolio_snapshot_id,
        "realized_trade_result_ids": (),
        "finalized_at": BASE.replace(minute=41),
    }
    finalization = ResultFinalizationPayload.model_validate(
        {"payload_id": calculate_marker_payload_id(finalization_content), **finalization_content}
    )
    return ReplayArtifactBundle.create(
        manifest=manifest,
        events=(
            replay_event(
                ReplayPhase.PORTFOLIO_UPDATE,
                portfolio.as_of,
                payload_id=portfolio.portfolio_snapshot_id,
            ),
            replay_event(
                ReplayPhase.RESULT_FINALIZATION,
                finalization.finalized_at,
                payload_id=finalization.payload_id,
            ),
        ),
        portfolio_snapshots=(portfolio,),
        finalizations=(finalization,),
    )
