import socket
from datetime import timedelta

import pytest
from pydantic import ValidationError
from strategy_helpers import evaluation_context, strategy_bars

from ai_trading_scanner.domain import AgentId
from ai_trading_scanner.indicators import IndicatorReason
from ai_trading_scanner.market_data import (
    DatasetValidator,
    QualityCode,
    QualityFinding,
    QualitySeverity,
    Timeframe,
)
from ai_trading_scanner.strategies import (
    REGISTERED_BASELINE_CONFIGURATIONS,
    MomentumConfiguration,
    MultiFactorConfiguration,
    NoTradeDecision,
    NoTradeReason,
    StrategyEvaluationContext,
    evaluate_strategy,
)


@pytest.mark.parametrize("configuration", REGISTERED_BASELINE_CONFIGURATIONS)
def test_indicator_not_ready_is_an_explicit_no_trade(configuration: object) -> None:
    config = configuration
    decision = evaluate_strategy(
        evaluation_context(
            config,  # type: ignore[arg-type]
            strategy_bars(["100"] * 60),
            unavailable_reason=IndicatorReason.INSUFFICIENT_HISTORY,
        ),
        config,  # type: ignore[arg-type]
    )

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.INDICATOR_NOT_READY,)


@pytest.mark.parametrize(
    "reason",
    [IndicatorReason.MISSING_INTERVAL, IndicatorReason.INCOMPLETE_SESSION_PREFIX],
)
def test_gap_or_incomplete_indicator_state_is_explicit(reason: IndicatorReason) -> None:
    configuration = MultiFactorConfiguration()
    decision = evaluate_strategy(
        evaluation_context(
            configuration,
            strategy_bars(["100"] * 60),
            unavailable_reason=reason,
        ),
        configuration,
    )

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.GAP_OR_INCOMPLETE_SESSION,)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (QualityCode.MISSING_INTERVAL, NoTradeReason.GAP_OR_INCOMPLETE_SESSION),
        (QualityCode.STALE_OBSERVATION, NoTradeReason.DATA_QUALITY_CONCERN),
    ],
)
def test_visible_quality_warnings_fail_to_observable_no_trade(
    code: QualityCode, expected: NoTradeReason
) -> None:
    configuration = MultiFactorConfiguration()
    warning = QualityFinding(
        code=code,
        severity=QualitySeverity.WARNING,
        message="causally visible test warning",
    )
    decision = evaluate_strategy(
        evaluation_context(configuration, strategy_bars(["100"] * 60), findings=(warning,)),
        configuration,
    )

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (expected,)
    assert decision.quality_findings == (warning,)


def test_future_quality_warning_is_rejected_at_context_boundary() -> None:
    configuration = MultiFactorConfiguration()
    bars = strategy_bars(["100"] * 60)
    base = evaluation_context(configuration, bars)
    warning = QualityFinding(
        code=QualityCode.MISSING_INTERVAL,
        severity=QualitySeverity.WARNING,
        message="future warning",
        start_at=base.as_of + timedelta(minutes=5),
        end_at=base.as_of + timedelta(minutes=10),
    )
    data = base.market_data.model_copy(update={"quality_findings": (warning,)})
    indicators = base.indicators.model_copy(
        update={
            name: series.model_copy(update={"quality_findings": (warning,)})
            for name, series in (
                ("ema_fast", base.indicators.ema_fast),
                ("ema_medium", base.indicators.ema_medium),
                ("ema_slow", base.indicators.ema_slow),
                ("rsi", base.indicators.rsi),
                ("atr", base.indicators.atr),
                ("session_vwap", base.indicators.session_vwap),
            )
        }
    )

    with pytest.raises(ValidationError, match="future quality finding"):
        StrategyEvaluationContext.model_validate(
            {**base.model_dump(mode="python"), "market_data": data, "indicators": indicators}
        )


def test_fatal_sequence_quality_fails_closed() -> None:
    configuration = MultiFactorConfiguration()
    context = evaluation_context(configuration, strategy_bars(["100"] * 60))
    duplicate = context.market_data.model_copy(
        update={"bars": (context.market_data.bars[0], context.market_data.bars[0])}
    )
    forged = context.model_copy(update={"market_data": duplicate})

    with pytest.raises(ValueError, match="fatal market-data quality"):
        evaluate_strategy(forged, configuration)


def test_explicit_fatal_finding_fails_closed() -> None:
    configuration = MultiFactorConfiguration()
    context = evaluation_context(configuration, strategy_bars(["100"] * 60))
    fatal = QualityFinding(
        code=QualityCode.MALFORMED_RECORD,
        severity=QualitySeverity.FATAL,
        message="fatal test finding",
    )
    data = context.market_data.model_copy(update={"quality_findings": (fatal,)})
    forged = context.model_copy(update={"market_data": data})

    with pytest.raises(ValueError, match="fatal market-data quality"):
        evaluate_strategy(forged, configuration)


def test_future_unavailable_bar_is_rejected_at_context_boundary() -> None:
    configuration = MultiFactorConfiguration()
    context = evaluation_context(configuration, strategy_bars(["100"] * 60))
    early = context.market_data.bars[-2].available_at
    data = context.market_data.model_copy(update={"as_of": early})

    with pytest.raises(ValidationError, match="causal inputs|future-unavailable"):
        StrategyEvaluationContext.model_validate(
            {**context.model_dump(mode="python"), "as_of": early, "market_data": data}
        )


def test_market_slice_hash_mismatch_is_rejected_at_context_boundary() -> None:
    configuration = MultiFactorConfiguration()
    context = evaluation_context(configuration, strategy_bars(["100"] * 60))
    forged_data = context.market_data.model_copy(update={"content_hash_sha256": "f" * 64})

    with pytest.raises(ValidationError, match="slice identity"):
        StrategyEvaluationContext.model_validate(
            {**context.model_dump(mode="python"), "market_data": forged_data}
        )


def test_indicator_point_lineage_must_match_every_causal_bar_field() -> None:
    configuration = MultiFactorConfiguration()
    context = evaluation_context(configuration, strategy_bars(["100"] * 60))
    point = context.indicators.ema_fast.points[-1].model_copy(
        update={"bar_start_at": context.indicators.ema_fast.points[-2].bar_start_at}
    )
    series = context.indicators.ema_fast.model_copy(
        update={"points": (*context.indicators.ema_fast.points[:-1], point)}
    )
    indicators = context.indicators.model_copy(update={"ema_fast": series})

    with pytest.raises(ValidationError, match="do not align"):
        StrategyEvaluationContext.model_validate(
            {**context.model_dump(mode="python"), "indicators": indicators}
        )


def test_non_authoritative_timeframe_fails_closed() -> None:
    configuration = MultiFactorConfiguration()
    context = evaluation_context(configuration, strategy_bars(["100"] * 60))
    wrong_bar = context.market_data.bars[-1].model_copy(update={"timeframe": Timeframe.MINUTE_1})
    forged_data = context.market_data.model_copy(
        update={"bars": (*context.market_data.bars[:-1], wrong_bar)}
    )
    forged = context.model_copy(update={"market_data": forged_data})

    with pytest.raises(ValueError, match="timeframe"):
        evaluate_strategy(forged, configuration)


def test_cross_session_strategy_slice_fails_closed() -> None:
    configuration = MultiFactorConfiguration()
    context = evaluation_context(configuration, strategy_bars(["100"] * 60))
    prior_session_bar = context.market_data.bars[0].model_copy(
        update={"session_id": "XNYS:2024-07-01"}
    )
    forged_data = context.market_data.model_copy(
        update={"bars": (prior_session_bar, *context.market_data.bars[1:])}
    )
    forged = context.model_copy(update={"market_data": forged_data})

    with pytest.raises(ValueError, match="single current-session"):
        evaluate_strategy(forged, configuration)


def test_non_authoritative_indicator_configuration_fails_closed() -> None:
    configuration = MultiFactorConfiguration()
    context = evaluation_context(configuration, strategy_bars(["100"] * 60))
    altered_configuration = context.indicators.ema_fast.configuration.model_copy(
        update={"implementation_version": "future-continuous-v2"}
    )
    altered_series = context.indicators.ema_fast.model_copy(
        update={"configuration": altered_configuration}
    )
    indicators = context.indicators.model_copy(update={"ema_fast": altered_series})
    forged = context.model_copy(update={"indicators": indicators})

    with pytest.raises(ValueError, match="indicator configuration"):
        evaluate_strategy(forged, configuration)


def test_undeclared_missing_interval_fails_closed() -> None:
    configuration = MultiFactorConfiguration()
    bars = strategy_bars(["100"] * 60)
    context = evaluation_context(configuration, (*bars[:20], *bars[21:]))

    with pytest.raises(ValueError, match="quality lineage omits"):
        evaluate_strategy(context, configuration)


def test_declared_missing_interval_produces_observable_no_trade() -> None:
    configuration = MultiFactorConfiguration()
    bars = strategy_bars(["100"] * 60)
    gapped = (*bars[:20], *bars[21:])
    validation = DatasetValidator().validate(
        gapped,
        coverage_start_at=gapped[0].start_at,
        coverage_end_at=gapped[-1].end_at,
    )

    decision = evaluate_strategy(
        evaluation_context(configuration, gapped, findings=validation.findings),
        configuration,
    )

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.GAP_OR_INCOMPLETE_SESSION,)
    assert decision.quality_findings == validation.findings


def test_strategy_decision_is_prefix_invariant_to_appended_future_bars() -> None:
    configuration = MultiFactorConfiguration()
    prefix = strategy_bars(["100"] * 59 + ["105"])
    future = strategy_bars(["999"])[0].model_copy(
        update={
            "start_at": prefix[-1].end_at,
            "end_at": prefix[-1].end_at + prefix[-1].timeframe.duration,
            "available_at": prefix[-1].available_at + prefix[-1].timeframe.duration,
        }
    )
    extended = (*prefix, future)
    before = evaluate_strategy(evaluation_context(configuration, prefix), configuration)
    same_causal_prefix = tuple(
        bar for bar in extended if bar.available_at <= prefix[-1].available_at
    )
    after_append = evaluate_strategy(
        evaluation_context(configuration, same_causal_prefix), configuration
    )

    assert before == after_append


@pytest.mark.parametrize("configuration", REGISTERED_BASELINE_CONFIGURATIONS)
def test_repeated_evaluation_is_deterministic_and_idempotent(configuration: object) -> None:
    config = configuration
    context = evaluation_context(config, strategy_bars(["100"] * 60))  # type: ignore[arg-type]

    assert evaluate_strategy(context, config) == evaluate_strategy(context, config)  # type: ignore[arg-type]


def test_stale_context_returns_no_trade() -> None:
    configuration = MultiFactorConfiguration(maximum_data_age_seconds=1)
    context = evaluation_context(configuration, strategy_bars(["100"] * 60))
    stale_as_of = context.as_of + timedelta(seconds=2)
    stale_data = context.market_data.model_copy(update={"as_of": stale_as_of})
    stale_indicators = context.indicators.model_copy(
        update={
            name: series.model_copy(update={"as_of": stale_as_of})
            for name, series in (
                ("ema_fast", context.indicators.ema_fast),
                ("ema_medium", context.indicators.ema_medium),
                ("ema_slow", context.indicators.ema_slow),
                ("rsi", context.indicators.rsi),
                ("atr", context.indicators.atr),
                ("session_vwap", context.indicators.session_vwap),
            )
        }
    )
    stale = context.model_copy(
        update={"as_of": stale_as_of, "market_data": stale_data, "indicators": stale_indicators}
    )

    decision = evaluate_strategy(stale, configuration)

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.UNSUPPORTED_CONTEXT,)


def test_strategy_configuration_mismatch_fails_closed() -> None:
    configuration = MomentumConfiguration()
    context = evaluation_context(configuration, strategy_bars(["100"] * 60))
    changed = MomentumConfiguration(pullback_lookback=6)

    with pytest.raises(ValueError, match="configuration identity differs"):
        evaluate_strategy(context, changed)


def test_all_four_agents_receive_equal_canonical_information() -> None:
    bars = strategy_bars(["100"] * 60)
    contexts = tuple(
        evaluation_context(
            configuration,
            bars,
            agent=f"agent:{letter}",
        )
        for configuration, letter in zip(
            REGISTERED_BASELINE_CONFIGURATIONS, ("A", "B", "C", "D"), strict=True
        )
    )

    assert len({context.market_data.content_hash_sha256 for context in contexts}) == 1
    assert len({context.indicators.configuration_ids for context in contexts}) == 1
    assert {context.agent_id for context in contexts} == {
        AgentId.parse("agent:A"),
        AgentId.parse("agent:B"),
        AgentId.parse("agent:C"),
        AgentId.parse("agent:D"),
    }


def test_evaluation_attempts_no_network_broker_or_ai_side_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("strategy evaluation attempted external I/O")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    configuration = MultiFactorConfiguration()
    context = evaluation_context(configuration, strategy_bars(["100"] * 60))

    decision = evaluate_strategy(context, configuration)

    assert decision.agent_id == AgentId.parse("agent:A")


def test_agent_attribution_changes_identity_without_changing_shared_inputs() -> None:
    configuration = MultiFactorConfiguration()
    bars = strategy_bars(["100"] * 60)
    first_context = evaluation_context(configuration, bars, agent="agent:A")
    second_context = evaluation_context(configuration, bars, agent="agent:B")

    first = evaluate_strategy(first_context, configuration)
    second = evaluate_strategy(second_context, configuration)

    assert first.agent_id != second.agent_id
    assert first.decision_id != second.decision_id
    assert first.market_data_slice_hash_sha256 == second.market_data_slice_hash_sha256
    assert first.indicator_configuration_ids == second.indicator_configuration_ids
