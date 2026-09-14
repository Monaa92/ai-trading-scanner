"""Pure deterministic evaluators for the four Phase 4 research baselines."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import Protocol

from ai_trading_scanner.indicators import (
    ATRConfig,
    EMAConfig,
    IndicatorReason,
    PriceBasis,
    ResetPolicy,
    RSIConfig,
    SmoothingMethod,
    VWAPConfig,
)
from ai_trading_scanner.market_data import DatasetValidator, QualityCode, QualitySeverity
from ai_trading_scanner.strategies.configurations import (
    BreakoutConfiguration,
    MeanReversionConfiguration,
    MomentumConfiguration,
    MultiFactorConfiguration,
    StrategyConfiguration,
    calculate_strategy_configuration_id,
)
from ai_trading_scanner.strategies.models import (
    EntryIntent,
    EvidenceItem,
    EvidenceValueType,
    ExpectedEconomics,
    ManagementStyle,
    ManagementTrigger,
    NoTradeDecision,
    NoTradeReason,
    ObjectiveIntent,
    ObjectiveKind,
    ProposalSide,
    SizingIntent,
    StrategyDecision,
    StrategyEvaluationContext,
    TradeProposal,
    TradeProposalDecision,
    calculate_strategy_decision_id,
    calculate_trade_proposal_id,
    create_management_mandate,
    latest_indicator_value,
)

_ARITHMETIC = Context(prec=34, rounding=ROUND_HALF_EVEN)


class StrategyEvaluator(Protocol):
    def evaluate(self, context: StrategyEvaluationContext) -> StrategyDecision: ...


def _boolean(name: str, value: bool) -> EvidenceItem:
    return EvidenceItem(name=name, value_type=EvidenceValueType.BOOLEAN, value=value)


def _decimal(name: str, value: Decimal, unit: str | None = None) -> EvidenceItem:
    return EvidenceItem(name=name, value_type=EvidenceValueType.DECIMAL, value=value, unit=unit)


def _text(name: str, value: str) -> EvidenceItem:
    return EvidenceItem(name=name, value_type=EvidenceValueType.TEXT, value=value)


def _base(
    context: StrategyEvaluationContext, configuration: StrategyConfiguration
) -> dict[str, object]:
    return {
        "schema_version": "strategy-decision-v1",
        "agent_id": context.agent_id,
        "strategy_id": configuration.strategy_id,
        "strategy_version": configuration.strategy_version,
        "strategy_configuration_id": context.strategy_configuration_id,
        "instrument_id": context.instrument_id,
        "as_of": context.as_of,
        "dataset_id": context.market_data.dataset_id,
        "market_data_slice_hash_sha256": context.market_data.content_hash_sha256,
        "indicator_configuration_ids": context.indicators.configuration_ids,
        "quality_findings": context.market_data.quality_findings,
    }


def _no_trade(
    context: StrategyEvaluationContext,
    configuration: StrategyConfiguration,
    reasons: tuple[NoTradeReason, ...],
    evidence: tuple[EvidenceItem, ...],
    detail: str | None = None,
) -> NoTradeDecision:
    content = {
        **_base(context, configuration),
        "outcome": "NO_TRADE",
        "reasons": reasons,
        "detail": detail,
        "proposal": None,
        "evidence": evidence,
    }
    return NoTradeDecision(
        decision_id=calculate_strategy_decision_id(content),
        **content,  # type: ignore[arg-type]
    )


def _proposal_decision(
    context: StrategyEvaluationContext,
    configuration: StrategyConfiguration,
    *,
    stop_level: Decimal,
    objective: ObjectiveIntent,
    gross_expected_return: Decimal,
    management_style: ManagementStyle,
    management_triggers: tuple[ManagementTrigger, ...],
    evidence: tuple[EvidenceItem, ...],
) -> StrategyDecision:
    cost = context.cost_estimate
    assert cost is not None
    with localcontext(_ARITHMETIC):
        economics = ExpectedEconomics(
            gross_expected_return=gross_expected_return,
            cost_estimate=cost,
            net_expected_return=gross_expected_return - cost.total_return_drag,
        )
    if economics.net_expected_return < configuration.minimum_expected_net_return:
        reason = (
            NoTradeReason.TRANSACTION_COST_CONCERN
            if gross_expected_return >= configuration.minimum_expected_net_return
            else NoTradeReason.EXPECTED_EDGE_TOO_SMALL
        )
        return _no_trade(
            context,
            configuration,
            (reason,),
            (
                *evidence,
                _decimal("gross_expected_return", gross_expected_return, "RETURN"),
                _decimal("cost_return_drag", cost.total_return_drag, "RETURN"),
                _decimal("net_expected_return", economics.net_expected_return, "RETURN"),
            ),
        )
    latest = context.market_data.bars[-1]
    mandate = create_management_mandate(management_style, management_triggers)
    proposal_content: dict[str, object] = {
        "schema_version": "trade-proposal-v1",
        "agent_id": context.agent_id,
        "strategy_id": configuration.strategy_id,
        "strategy_version": configuration.strategy_version,
        "strategy_configuration_id": context.strategy_configuration_id,
        "instrument_id": context.instrument_id,
        "side": ProposalSide.LONG,
        "generated_at": context.as_of,
        "as_of": context.as_of,
        "valid_until": latest.end_at
        + latest.timeframe.duration * configuration.proposal_validity_intervals,
        "dataset_id": context.market_data.dataset_id,
        "market_data_slice_hash_sha256": context.market_data.content_hash_sha256,
        "indicator_configuration_ids": context.indicators.configuration_ids,
        "entry": EntryIntent(reference_price=latest.close, currency=latest.currency),
        "sizing": SizingIntent(),
        "stop_level": stop_level,
        "objective": objective,
        "management_mandate": mandate,
        "economics": economics,
        "evidence": evidence,
        "quality_findings": context.market_data.quality_findings,
        "authority_context": context.authority_context,
    }
    if proposal_content["valid_until"] <= context.as_of:  # type: ignore[operator]
        return _no_trade(
            context,
            configuration,
            (NoTradeReason.UNSUPPORTED_CONTEXT,),
            (*evidence, _text("context_status", "PROPOSAL_ALREADY_EXPIRED")),
        )
    proposal = TradeProposal(
        proposal_id=calculate_trade_proposal_id(proposal_content),
        **proposal_content,  # type: ignore[arg-type]
    )
    decision_content = {
        **_base(context, configuration),
        "outcome": "TRADE_PROPOSAL",
        "reasons": (),
        "detail": None,
        "proposal": proposal,
        "evidence": evidence,
    }
    return TradeProposalDecision(
        decision_id=calculate_strategy_decision_id(decision_content),
        **decision_content,  # type: ignore[arg-type]
    )


def _validate_context(
    context: StrategyEvaluationContext, configuration: StrategyConfiguration
) -> StrategyDecision | None:
    expected_configuration_id = calculate_strategy_configuration_id(configuration)
    if context.strategy_id != configuration.strategy_id:
        raise ValueError("evaluation context strategy identity differs from configuration")
    if context.strategy_configuration_id != expected_configuration_id:
        raise ValueError("evaluation context strategy configuration identity differs")
    if any(bar.timeframe is not configuration.timeframe for bar in context.market_data.bars):
        raise ValueError("market-data timeframe does not match strategy configuration")
    bars = context.market_data.bars
    if any(bar.session_id != bars[-1].session_id for bar in bars):
        raise ValueError("strategy evaluation requires a single current-session slice")
    validation = DatasetValidator().validate(
        bars,
        coverage_start_at=bars[0].start_at,
        coverage_end_at=bars[-1].end_at,
    )
    if not validation.usable or any(
        finding.severity is QualitySeverity.FATAL
        for finding in context.market_data.quality_findings
    ):
        raise ValueError("strategy input contains fatal market-data quality findings")
    undeclared_findings = tuple(
        finding
        for finding in validation.findings
        if finding not in context.market_data.quality_findings
    )
    if undeclared_findings:
        raise ValueError("strategy input quality lineage omits detected findings")
    configurations = (
        context.indicators.ema_fast.configuration,
        context.indicators.ema_medium.configuration,
        context.indicators.ema_slow.configuration,
        context.indicators.rsi.configuration,
        context.indicators.atr.configuration,
        context.indicators.session_vwap.configuration,
    )
    expected_configurations = (
        EMAConfig(period=configuration.ema_fast_period),
        EMAConfig(period=configuration.ema_medium_period),
        EMAConfig(period=configuration.ema_slow_period),
        RSIConfig(period=configuration.rsi_period, smoothing=SmoothingMethod.WILDER),
        ATRConfig(period=configuration.atr_period, smoothing=SmoothingMethod.WILDER),
        VWAPConfig(
            price_basis=PriceBasis.TYPICAL_PRICE,
            reset_policy=ResetPolicy.SESSION,
        ),
    )
    if configurations != expected_configurations:
        raise ValueError("indicator configuration does not match strategy configuration")
    latest_bar = context.market_data.bars[-1]
    if any(
        series.points[-1].bar_end_at != latest_bar.end_at
        for series in context.indicators.all_series
    ):
        raise ValueError("indicator snapshot is not aligned to the latest causal bar")
    if context.as_of - latest_bar.available_at > timedelta(
        seconds=configuration.maximum_data_age_seconds
    ):
        return _no_trade(
            context,
            configuration,
            (NoTradeReason.UNSUPPORTED_CONTEXT,),
            (_text("context_status", "STALE_MARKET_DATA"),),
        )
    warnings = tuple(
        finding
        for finding in context.market_data.quality_findings
        if finding.severity is QualitySeverity.WARNING
    )
    if warnings:
        reason = (
            NoTradeReason.GAP_OR_INCOMPLETE_SESSION
            if any(finding.code is QualityCode.MISSING_INTERVAL for finding in warnings)
            else NoTradeReason.DATA_QUALITY_CONCERN
        )
        return _no_trade(
            context,
            configuration,
            (reason,),
            (_text("quality_status", ",".join(item.code.value for item in warnings)),),
        )
    unavailable = tuple(
        series.points[-1].reason
        for series in context.indicators.all_series
        if latest_indicator_value(series) is None
    )
    if unavailable:
        reason = (
            NoTradeReason.GAP_OR_INCOMPLETE_SESSION
            if any(
                item
                in {
                    IndicatorReason.MISSING_INTERVAL,
                    IndicatorReason.INCOMPLETE_SESSION_PREFIX,
                }
                for item in unavailable
            )
            else NoTradeReason.INDICATOR_NOT_READY
        )
        return _no_trade(
            context,
            configuration,
            (reason,),
            (_text("indicator_status", ",".join(item.value for item in unavailable)),),
        )
    if context.cost_estimate is None:
        return _no_trade(
            context,
            configuration,
            (NoTradeReason.UNSUPPORTED_CONTEXT,),
            (_text("cost_status", "ROUND_TRIP_ESTIMATE_REQUIRED"),),
        )
    return None


def _values(context: StrategyEvaluationContext) -> tuple[Decimal, ...]:
    values = tuple(latest_indicator_value(series) for series in context.indicators.all_series)
    assert all(value is not None for value in values)
    return tuple(value for value in values if value is not None)


class MomentumEvaluator:
    def __init__(self, configuration: MomentumConfiguration) -> None:
        self.configuration = configuration

    def evaluate(self, context: StrategyEvaluationContext) -> StrategyDecision:
        blocked = _validate_context(context, self.configuration)
        if blocked is not None:
            return blocked
        fast, medium, slow, rsi, atr, vwap = _values(context)
        bars = context.market_data.bars
        latest = bars[-1]
        trend_aligned = latest.close > vwap and fast > medium > slow
        rsi_qualifies = self.configuration.minimum_rsi <= rsi <= self.configuration.maximum_rsi
        evidence: tuple[EvidenceItem, ...] = (
            _boolean("trend_aligned", trend_aligned),
            _boolean("rsi_qualifies", rsi_qualifies),
            _decimal("rsi", rsi, "PERCENT"),
        )
        if not trend_aligned:
            bearish = latest.close < vwap and fast < medium < slow
            return _no_trade(
                context,
                self.configuration,
                (
                    NoTradeReason.UNAUTHORIZED_DIRECTION
                    if bearish
                    else NoTradeReason.CONFLICTING_FACTORS,
                ),
                evidence,
            )
        if not rsi_qualifies:
            return _no_trade(
                context,
                self.configuration,
                (NoTradeReason.INSUFFICIENT_SIGNAL,),
                evidence,
            )
        needed = max(
            self.configuration.pullback_lookback + 1,
            self.configuration.resistance_lookback + 1,
            self.configuration.confirmation_bars + 1,
        )
        if len(bars) < needed:
            return _no_trade(
                context,
                self.configuration,
                (NoTradeReason.INSUFFICIENT_CONFIRMATION,),
                (*evidence, _decimal("available_bars", Decimal(len(bars)), "COUNT")),
            )
        medium_points = context.indicators.ema_medium.points
        slow_points = context.indicators.ema_slow.points
        pullback_found = any(
            bar.low <= medium_point.value and bar.close >= slow_point.value
            for bar, medium_point, slow_point in zip(
                bars[-self.configuration.pullback_lookback - 1 : -1],
                medium_points[-self.configuration.pullback_lookback - 1 : -1],
                slow_points[-self.configuration.pullback_lookback - 1 : -1],
                strict=True,
            )
            if medium_point.value is not None and slow_point.value is not None
        )
        trigger_confirmed = latest.close > fast and all(
            bars[-offset].close > bars[-offset - 1].high
            for offset in range(1, self.configuration.confirmation_bars + 1)
        )
        evidence += (
            _boolean("pullback_found", pullback_found),
            _boolean("trigger_confirmed", trigger_confirmed),
        )
        if not pullback_found or not trigger_confirmed:
            return _no_trade(
                context,
                self.configuration,
                (NoTradeReason.INSUFFICIENT_CONFIRMATION,),
                evidence,
            )
        resistance_candidates = tuple(
            bar.high
            for bar in bars[-self.configuration.resistance_lookback - 1 : -1]
            if bar.high > latest.close
        )
        if not resistance_candidates:
            return _no_trade(
                context,
                self.configuration,
                (NoTradeReason.STRATEGY_INVALIDATED,),
                (*evidence, _text("resistance_status", "NO_CAUSAL_LEVEL_ABOVE_ENTRY")),
            )
        target = min(resistance_candidates)
        with localcontext(_ARITHMETIC):
            stop = (
                min(bar.low for bar in bars[-self.configuration.pullback_lookback - 1 :])
                - self.configuration.stop_atr_buffer * atr
            )
            gross = (target - latest.close) / latest.close
        if stop <= 0 or stop >= latest.close:
            raise ValueError("momentum strategy produced invalid stop geometry")
        return _proposal_decision(
            context,
            self.configuration,
            stop_level=stop,
            objective=ObjectiveIntent(
                kind=ObjectiveKind.RESISTANCE_LEVEL,
                reference_level=target,
                is_mandatory_exit=True,
            ),
            gross_expected_return=gross,
            management_style=ManagementStyle.MOMENTUM_TREND,
            management_triggers=(
                ManagementTrigger.PROTECTIVE_STOP,
                ManagementTrigger.TARGET_REACHED,
                ManagementTrigger.TREND_INVALIDATED,
                ManagementTrigger.MOMENTUM_DETERIORATED,
                ManagementTrigger.TRAILING_PROTECTION,
            ),
            evidence=(*evidence, _decimal("resistance_level", target, "PRICE")),
        )


class MeanReversionEvaluator:
    def __init__(self, configuration: MeanReversionConfiguration) -> None:
        self.configuration = configuration

    def evaluate(self, context: StrategyEvaluationContext) -> StrategyDecision:
        blocked = _validate_context(context, self.configuration)
        if blocked is not None:
            return blocked
        fast, medium, slow, rsi, atr, vwap = _values(context)
        bars = context.market_data.bars
        latest = bars[-1]
        with localcontext(_ARITHMETIC):
            deviation = vwap - latest.close
            required_deviation = self.configuration.deviation_atr_multiple * atr
        overextended = deviation >= required_deviation and rsi <= self.configuration.oversold_rsi
        strong_downtrend = fast < medium < slow and latest.close < fast
        confirmation = len(bars) > self.configuration.confirmation_bars and all(
            bars[-offset].close > bars[-offset - 1].close
            for offset in range(1, self.configuration.confirmation_bars + 1)
        )
        evidence = (
            _decimal("deviation_from_vwap", deviation, "PRICE"),
            _decimal("required_deviation", required_deviation, "PRICE"),
            _boolean("overextended", overextended),
            _boolean("strong_downtrend", strong_downtrend),
            _boolean("reversion_confirmed", confirmation),
        )
        if strong_downtrend:
            return _no_trade(
                context,
                self.configuration,
                (NoTradeReason.UNSUITABLE_REGIME,),
                evidence,
            )
        if not overextended:
            return _no_trade(
                context,
                self.configuration,
                (NoTradeReason.INSUFFICIENT_SIGNAL,),
                evidence,
            )
        if not confirmation:
            return _no_trade(
                context,
                self.configuration,
                (NoTradeReason.INSUFFICIENT_CONFIRMATION,),
                evidence,
            )
        with localcontext(_ARITHMETIC):
            stop = min(bar.low for bar in bars[-self.configuration.confirmation_bars - 1 :]) - (
                self.configuration.stop_atr_multiple * atr
            )
            gross = (vwap - latest.close) / latest.close
        if stop <= 0 or stop >= latest.close:
            raise ValueError("mean-reversion strategy produced invalid stop geometry")
        return _proposal_decision(
            context,
            self.configuration,
            stop_level=stop,
            objective=ObjectiveIntent(
                kind=ObjectiveKind.REVERSION_LEVEL,
                reference_level=vwap,
                is_mandatory_exit=True,
            ),
            gross_expected_return=gross,
            management_style=ManagementStyle.MEAN_REVERSION,
            management_triggers=(
                ManagementTrigger.PROTECTIVE_STOP,
                ManagementTrigger.MEAN_REACHED,
                ManagementTrigger.THESIS_INVALIDATED,
            ),
            evidence=evidence,
        )


class BreakoutEvaluator:
    def __init__(self, configuration: BreakoutConfiguration) -> None:
        self.configuration = configuration

    def evaluate(self, context: StrategyEvaluationContext) -> StrategyDecision:
        blocked = _validate_context(context, self.configuration)
        if blocked is not None:
            return blocked
        *_, atr, _vwap = _values(context)
        bars = context.market_data.bars
        needed = self.configuration.range_lookback + self.configuration.confirmation_bars
        if len(bars) < needed:
            return _no_trade(
                context,
                self.configuration,
                (NoTradeReason.INSUFFICIENT_CONFIRMATION,),
                (_decimal("available_bars", Decimal(len(bars)), "COUNT"),),
            )
        reference_bars = bars[-needed : -self.configuration.confirmation_bars]
        confirmation_bars = bars[-self.configuration.confirmation_bars :]
        reference_high = max(bar.high for bar in reference_bars)
        breakout_confirmed = all(bar.close > reference_high for bar in confirmation_bars)
        average_volume = sum((bar.volume for bar in reference_bars), Decimal(0)) / Decimal(
            len(reference_bars)
        )
        required_volume = average_volume * self.configuration.minimum_volume_multiple
        volume_confirmed = confirmation_bars[-1].volume >= required_volume
        evidence = (
            _decimal("reference_high", reference_high, "PRICE"),
            _boolean("breakout_confirmed", breakout_confirmed),
            _boolean("volume_confirmed", volume_confirmed),
        )
        if not breakout_confirmed:
            reason = (
                NoTradeReason.INSUFFICIENT_CONFIRMATION
                if confirmation_bars[-1].close > reference_high
                else NoTradeReason.INSUFFICIENT_SIGNAL
            )
            return _no_trade(context, self.configuration, (reason,), evidence)
        if not volume_confirmed:
            return _no_trade(
                context,
                self.configuration,
                (NoTradeReason.INSUFFICIENT_CONFIRMATION,),
                evidence,
            )
        latest = bars[-1]
        with localcontext(_ARITHMETIC):
            stop = reference_high - self.configuration.stop_atr_buffer * atr
            gross = self.configuration.expected_move_atr_multiple * atr / latest.close
        if stop <= 0 or stop >= latest.close:
            raise ValueError("breakout strategy produced invalid stop geometry")
        return _proposal_decision(
            context,
            self.configuration,
            stop_level=stop,
            objective=ObjectiveIntent(kind=ObjectiveKind.BREAKOUT_CONTINUATION),
            gross_expected_return=gross,
            management_style=ManagementStyle.BREAKOUT_CONTINUATION,
            management_triggers=(
                ManagementTrigger.PROTECTIVE_STOP,
                ManagementTrigger.BREAKOUT_FAILED,
                ManagementTrigger.RANGE_REENTRY,
                ManagementTrigger.TRAILING_PROTECTION,
            ),
            evidence=evidence,
        )


class MultiFactorEvaluator:
    def __init__(self, configuration: MultiFactorConfiguration) -> None:
        self.configuration = configuration

    def evaluate(self, context: StrategyEvaluationContext) -> StrategyDecision:
        blocked = _validate_context(context, self.configuration)
        if blocked is not None:
            return blocked
        fast, medium, slow, rsi, atr, vwap = _values(context)
        latest = context.market_data.bars[-1]
        trend = fast > medium > slow
        momentum = (
            self.configuration.momentum_minimum_rsi
            <= rsi
            <= self.configuration.momentum_maximum_rsi
        )
        above_vwap = latest.close > vwap
        with localcontext(_ARITHMETIC):
            volatility_usable = atr / latest.close <= self.configuration.maximum_atr_return
            contributions = (
                ("trend", self.configuration.trend_weight if trend else Decimal(0)),
                (
                    "momentum",
                    self.configuration.momentum_weight if momentum else Decimal(0),
                ),
                ("vwap", self.configuration.vwap_weight if above_vwap else Decimal(0)),
                (
                    "volatility",
                    self.configuration.volatility_weight if volatility_usable else Decimal(0),
                ),
            )
            score = sum((value for _, value in contributions), Decimal(0))
        evidence = (
            *(_decimal(f"{name}_contribution", value, "SCORE") for name, value in contributions),
            _decimal("combined_score", score, "SCORE"),
        )
        if score < self.configuration.minimum_combined_score:
            reason = (
                NoTradeReason.CONFLICTING_FACTORS
                if score > 0
                else NoTradeReason.INSUFFICIENT_SIGNAL
            )
            return _no_trade(context, self.configuration, (reason,), evidence)
        with localcontext(_ARITHMETIC):
            stop = latest.close - self.configuration.stop_atr_multiple * atr
            gross = self.configuration.expected_move_atr_multiple * atr / latest.close
        if stop <= 0 or stop >= latest.close:
            raise ValueError("multi-factor strategy produced invalid stop geometry")
        return _proposal_decision(
            context,
            self.configuration,
            stop_level=stop,
            objective=ObjectiveIntent(kind=ObjectiveKind.MULTI_FACTOR_THESIS),
            gross_expected_return=gross,
            management_style=ManagementStyle.MULTI_FACTOR_DYNAMIC,
            management_triggers=(
                ManagementTrigger.PROTECTIVE_STOP,
                ManagementTrigger.FACTORS_DETERIORATED,
                ManagementTrigger.THESIS_INVALIDATED,
            ),
            evidence=evidence,
        )


_EVALUATORS: dict[type[object], Callable[[object], StrategyEvaluator]] = {
    MomentumConfiguration: lambda config: MomentumEvaluator(config),  # type: ignore[arg-type]
    MeanReversionConfiguration: lambda config: MeanReversionEvaluator(config),  # type: ignore[arg-type]
    BreakoutConfiguration: lambda config: BreakoutEvaluator(config),  # type: ignore[arg-type]
    MultiFactorConfiguration: lambda config: MultiFactorEvaluator(config),  # type: ignore[arg-type]
}


def evaluator_for(configuration: StrategyConfiguration) -> StrategyEvaluator:
    factory = _EVALUATORS.get(type(configuration))
    if factory is None:
        raise TypeError(f"unsupported strategy configuration: {type(configuration).__name__}")
    return factory(configuration)


def evaluate_strategy(
    context: StrategyEvaluationContext, configuration: StrategyConfiguration
) -> StrategyDecision:
    """Evaluate without I/O, mutation, broker, risk, portfolio, or AI access."""
    return evaluator_for(configuration).evaluate(context)
