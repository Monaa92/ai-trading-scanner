"""Hand-auditable Phase 4 strategy contract fixtures."""

import hashlib
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from ai_trading_scanner.domain import AgentId, ConfigurationVersionId, DatasetId, InstrumentId
from ai_trading_scanner.domain.content_identity import canonical_json_bytes
from ai_trading_scanner.domain.execution import (
    ApprovalPolicy,
    DataRunMode,
    ExecutionDimensions,
    ExecutionEnvironment,
    OperatingContext,
    SubmissionMode,
)
from ai_trading_scanner.indicators import (
    ATRConfig,
    EMAConfig,
    IndicatorPoint,
    IndicatorReason,
    IndicatorSeries,
    IndicatorUnit,
    PriceBasis,
    ResetPolicy,
    RSIConfig,
    SmoothingMethod,
    VWAPConfig,
    calculate_indicator_configuration_id,
)
from ai_trading_scanner.market_data import (
    AvailabilityMode,
    HistoricalBar,
    MarketDataSlice,
    QualityFinding,
    Timeframe,
    UsEquitiesCalendar,
)
from ai_trading_scanner.strategies import (
    IndicatorSnapshot,
    ProposalAuthorityContext,
    RoundTripCostEstimate,
    StrategyConfiguration,
    StrategyEvaluationContext,
    calculate_strategy_configuration_id,
)


def strategy_bars(
    closes: Sequence[str],
    *,
    highs: Sequence[str] | None = None,
    lows: Sequence[str] | None = None,
    volumes: Sequence[str] | None = None,
) -> tuple[HistoricalBar, ...]:
    session = UsEquitiesCalendar().session_for_date(date(2024, 7, 2))
    assert session is not None
    high_values = highs or [str(Decimal(value) + Decimal("0.5")) for value in closes]
    low_values = lows or [str(Decimal(value) - Decimal("0.5")) for value in closes]
    volume_values = volumes or ["100"] * len(closes)
    return tuple(
        HistoricalBar(
            instrument_id=InstrumentId.parse("XNYS:SYNTH"),
            session_id=session.session_id,
            timeframe=Timeframe.MINUTE_5,
            start_at=session.open_at + timedelta(minutes=index * 5),
            end_at=session.open_at + timedelta(minutes=(index + 1) * 5),
            open=Decimal(close),
            high=Decimal(high),
            low=Decimal(low),
            close=Decimal(close),
            volume=Decimal(volume),
            currency="USD",
            source_record_id=f"strategy-{index}",
            received_at=None,
            available_at=session.open_at + timedelta(minutes=(index + 1) * 5, seconds=5),
            ingested_at=datetime(2024, 12, 31, tzinfo=UTC),
            availability_mode=AvailabilityMode.MODELED,
        )
        for index, (close, high, low, volume) in enumerate(
            zip(closes, high_values, low_values, volume_values, strict=True)
        )
    )


def market_slice(
    bars: Sequence[HistoricalBar], findings: tuple[QualityFinding, ...] = ()
) -> MarketDataSlice:
    frozen = tuple(bars)
    return MarketDataSlice(
        dataset_id=DatasetId.parse("sha256:" + "a" * 64),
        as_of=frozen[-1].available_at,
        bars=frozen,
        content_hash_sha256=hashlib.sha256(canonical_json_bytes(frozen)).hexdigest(),
        quality_findings=findings,
    )


def _series(
    data: MarketDataSlice,
    configuration: EMAConfig | RSIConfig | ATRConfig | VWAPConfig,
    value: Decimal | None,
    *,
    reason: IndicatorReason = IndicatorReason.READY,
) -> IndicatorSeries:
    configuration_id = calculate_indicator_configuration_id(configuration)
    points = tuple(
        IndicatorPoint(
            instrument_id=bar.instrument_id,
            timeframe=bar.timeframe,
            session_id=bar.session_id,
            bar_start_at=bar.start_at,
            bar_end_at=bar.end_at,
            bar_available_at=bar.available_at,
            configuration_id=configuration_id,
            value=value,
            ready=value is not None,
            reason=reason if value is None else IndicatorReason.READY,
        )
        for bar in data.bars
    )
    return IndicatorSeries(
        dataset_id=data.dataset_id,
        input_slice_hash_sha256=data.content_hash_sha256,
        as_of=data.as_of,
        latest_available_at=data.bars[-1].available_at,
        configuration=configuration,
        configuration_id=configuration_id,
        unit=(
            IndicatorUnit.PERCENT if isinstance(configuration, RSIConfig) else IndicatorUnit.PRICE
        ),
        points=points,
        quality_findings=data.quality_findings,
    )


def evaluation_context(
    configuration: StrategyConfiguration,
    bars: Sequence[HistoricalBar],
    *,
    agent: str = "agent:A",
    fast: str = "104",
    medium: str = "102",
    slow: str = "100",
    rsi: str = "60",
    atr: str = "1",
    vwap: str = "101",
    findings: tuple[QualityFinding, ...] = (),
    unavailable_reason: IndicatorReason | None = None,
    costs: RoundTripCostEstimate | None = None,
    include_costs: bool = True,
) -> StrategyEvaluationContext:
    data = market_slice(bars, findings)
    reason = unavailable_reason or IndicatorReason.READY
    unavailable = unavailable_reason is not None
    indicators = IndicatorSnapshot(
        ema_fast=_series(
            data,
            EMAConfig(period=configuration.ema_fast_period),
            None if unavailable else Decimal(fast),
            reason=reason,
        ),
        ema_medium=_series(
            data,
            EMAConfig(period=configuration.ema_medium_period),
            None if unavailable else Decimal(medium),
            reason=reason,
        ),
        ema_slow=_series(
            data,
            EMAConfig(period=configuration.ema_slow_period),
            None if unavailable else Decimal(slow),
            reason=reason,
        ),
        rsi=_series(
            data,
            RSIConfig(period=configuration.rsi_period, smoothing=SmoothingMethod.WILDER),
            None if unavailable else Decimal(rsi),
            reason=reason,
        ),
        atr=_series(
            data,
            ATRConfig(period=configuration.atr_period, smoothing=SmoothingMethod.WILDER),
            None if unavailable else Decimal(atr),
            reason=reason,
        ),
        session_vwap=_series(
            data,
            VWAPConfig(
                price_basis=PriceBasis.TYPICAL_PRICE,
                reset_policy=ResetPolicy.SESSION,
            ),
            None if unavailable else Decimal(vwap),
            reason=reason,
        ),
    )
    supplied_costs = (costs or zeroish_costs()) if include_costs else None
    return StrategyEvaluationContext(
        agent_id=AgentId.parse(agent),
        strategy_id=configuration.strategy_id,
        strategy_configuration_id=calculate_strategy_configuration_id(configuration),
        instrument_id=data.bars[-1].instrument_id,
        as_of=data.as_of,
        market_data=data,
        indicators=indicators,
        cost_estimate=supplied_costs,
        authority_context=ProposalAuthorityContext(
            configuration_version_id=ConfigurationVersionId.parse("phase4-fixture-v1"),
            execution_dimensions=ExecutionDimensions(
                data_run_mode=DataRunMode.HISTORICAL_REPLAY,
                execution_environment=ExecutionEnvironment.SIMULATION,
                submission_mode=SubmissionMode.SIGNAL_ONLY,
                approval_policy=ApprovalPolicy.MANUAL_APPROVAL,
                operating_context=OperatingContext.NORMAL,
            ),
        ),
    )


def zeroish_costs() -> RoundTripCostEstimate:
    return RoundTripCostEstimate(
        methodology_version_id=ConfigurationVersionId.parse("fixture-costs-v1"),
        entry_cost_return=Decimal("0.0001"),
        exit_cost_return=Decimal("0.0001"),
        spread_return=Decimal("0.0001"),
        slippage_return=Decimal("0.0001"),
    )
