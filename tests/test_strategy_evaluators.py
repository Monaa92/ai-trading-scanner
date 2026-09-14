from decimal import Decimal

import pytest
from strategy_helpers import evaluation_context, strategy_bars

from ai_trading_scanner.domain import ConfigurationVersionId
from ai_trading_scanner.market_data import HistoricalBar
from ai_trading_scanner.strategies import (
    BreakoutConfiguration,
    MeanReversionConfiguration,
    MomentumConfiguration,
    MultiFactorConfiguration,
    NoTradeDecision,
    NoTradeReason,
    ObjectiveKind,
    RoundTripCostEstimate,
    StrategyConfiguration,
    TradeProposalDecision,
    evaluate_strategy,
)


def test_momentum_proposes_only_complete_long_trend_pullback() -> None:
    configuration = MomentumConfiguration()
    closes = ["100"] * 54 + ["101", "102", "101", "102", "103", "105"]
    highs = [str(Decimal(close) + Decimal("0.5")) for close in closes]
    highs[50] = "110"
    highs[-2] = "104"
    highs[-1] = "105.5"
    lows = ["99.5"] * 60
    lows[-4] = "100.5"

    decision = evaluate_strategy(
        evaluation_context(configuration, strategy_bars(closes, highs=highs, lows=lows)),
        configuration,
    )

    assert isinstance(decision, TradeProposalDecision)
    assert decision.proposal.objective.kind is ObjectiveKind.RESISTANCE_LEVEL
    assert decision.proposal.objective.reference_level == Decimal("110")
    assert decision.proposal.stop_level < decision.proposal.entry.reference_price


@pytest.mark.parametrize(
    ("fast", "medium", "slow", "vwap", "expected_reason"),
    [
        ("98", "99", "100", "101", NoTradeReason.UNAUTHORIZED_DIRECTION),
        ("102", "104", "100", "101", NoTradeReason.CONFLICTING_FACTORS),
        ("100", "100", "100", "100", NoTradeReason.CONFLICTING_FACTORS),
    ],
)
def test_momentum_rejects_falling_conflicting_and_flat_contexts(
    fast: str,
    medium: str,
    slow: str,
    vwap: str,
    expected_reason: NoTradeReason,
) -> None:
    configuration = MomentumConfiguration()
    decision = evaluate_strategy(
        evaluation_context(
            configuration,
            strategy_bars(["100"] * 60),
            fast=fast,
            medium=medium,
            slow=slow,
            vwap=vwap,
        ),
        configuration,
    )

    assert isinstance(decision, NoTradeDecision)
    assert expected_reason in decision.reasons


def test_momentum_requires_pullback_trigger_and_causal_resistance() -> None:
    configuration = MomentumConfiguration()
    closes = ["100"] * 59 + ["105"]
    decision = evaluate_strategy(
        evaluation_context(configuration, strategy_bars(closes)), configuration
    )

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.STRATEGY_INVALIDATED,)


def test_mean_reversion_proposes_after_overextension_and_recovery() -> None:
    configuration = MeanReversionConfiguration()
    bars = strategy_bars(["100"] * 58 + ["89", "90"])

    decision = evaluate_strategy(
        evaluation_context(
            configuration,
            bars,
            fast="95",
            medium="96",
            slow="94",
            rsi="25",
            atr="2",
            vwap="100",
        ),
        configuration,
    )

    assert isinstance(decision, TradeProposalDecision)
    assert decision.proposal.objective.kind is ObjectiveKind.REVERSION_LEVEL
    assert decision.proposal.objective.reference_level == Decimal("100")


def test_mean_reversion_rejects_insufficient_deviation() -> None:
    configuration = MeanReversionConfiguration()
    decision = evaluate_strategy(
        evaluation_context(
            configuration,
            strategy_bars(["100"] * 60),
            fast="100",
            medium="100",
            slow="100",
            rsi="25",
            atr="2",
            vwap="101",
        ),
        configuration,
    )

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.INSUFFICIENT_SIGNAL,)


def test_mean_reversion_rejects_strong_downtrend_even_when_oversold() -> None:
    configuration = MeanReversionConfiguration()
    decision = evaluate_strategy(
        evaluation_context(
            configuration,
            strategy_bars(["100"] * 58 + ["89", "90"]),
            fast="95",
            medium="97",
            slow="99",
            rsi="20",
            atr="2",
            vwap="100",
        ),
        configuration,
    )

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.UNSUITABLE_REGIME,)


def test_mean_reversion_requires_confirmation() -> None:
    configuration = MeanReversionConfiguration()
    decision = evaluate_strategy(
        evaluation_context(
            configuration,
            strategy_bars(["100"] * 58 + ["91", "90"]),
            fast="95",
            medium="96",
            slow="94",
            rsi="20",
            atr="2",
            vwap="100",
        ),
        configuration,
    )

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.INSUFFICIENT_CONFIRMATION,)


def breakout_bars(*, confirmations: int = 2, high_volume: bool = True) -> tuple[HistoricalBar, ...]:
    closes = ["99"] * 20 + ["101"] * confirmations
    volumes = ["100"] * 20 + (["200"] * confirmations if high_volume else ["100"] * confirmations)
    return strategy_bars(closes, volumes=volumes)


def test_breakout_requires_two_confirmed_closes_and_volume() -> None:
    configuration = BreakoutConfiguration()
    decision = evaluate_strategy(evaluation_context(configuration, breakout_bars()), configuration)

    assert isinstance(decision, TradeProposalDecision)
    assert decision.proposal.objective.kind is ObjectiveKind.BREAKOUT_CONTINUATION
    assert decision.proposal.objective.is_mandatory_exit is False


def test_breakout_rejects_single_bar_breakout() -> None:
    configuration = BreakoutConfiguration()
    bars = strategy_bars(["99"] * 21 + ["101"], volumes=["100"] * 21 + ["200"])
    decision = evaluate_strategy(evaluation_context(configuration, bars), configuration)

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.INSUFFICIENT_CONFIRMATION,)


def test_breakout_rejects_weak_volume_confirmation() -> None:
    configuration = BreakoutConfiguration()
    decision = evaluate_strategy(
        evaluation_context(configuration, breakout_bars(high_volume=False)), configuration
    )

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.INSUFFICIENT_CONFIRMATION,)


def test_breakout_rejects_no_breakout() -> None:
    configuration = BreakoutConfiguration()
    decision = evaluate_strategy(
        evaluation_context(configuration, strategy_bars(["99"] * 22)), configuration
    )

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.INSUFFICIENT_SIGNAL,)


def test_multi_factor_exposes_named_contributions_and_proposes_when_aligned() -> None:
    configuration = MultiFactorConfiguration()
    decision = evaluate_strategy(
        evaluation_context(configuration, strategy_bars(["100"] * 59 + ["105"])),
        configuration,
    )

    assert isinstance(decision, TradeProposalDecision)
    assert {item.name for item in decision.evidence} == {
        "trend_contribution",
        "momentum_contribution",
        "vwap_contribution",
        "volatility_contribution",
        "combined_score",
    }
    assert decision.proposal.objective.kind is ObjectiveKind.MULTI_FACTOR_THESIS


def test_multi_factor_retains_conflicts_and_returns_no_trade() -> None:
    configuration = MultiFactorConfiguration()
    decision = evaluate_strategy(
        evaluation_context(
            configuration,
            strategy_bars(["100"] * 60),
            fast="101",
            medium="102",
            slow="103",
            rsi="60",
            vwap="101",
        ),
        configuration,
    )

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.CONFLICTING_FACTORS,)
    assert len(decision.evidence) == 5


@pytest.mark.parametrize(
    "configuration",
    [
        MomentumConfiguration(),
        MeanReversionConfiguration(),
        BreakoutConfiguration(),
        MultiFactorConfiguration(),
    ],
)
def test_missing_round_trip_cost_estimate_fails_to_no_trade(
    configuration: StrategyConfiguration,
) -> None:
    config = configuration
    context = evaluation_context(
        config,
        strategy_bars(["100"] * 60),
        include_costs=False,
    )
    decision = evaluate_strategy(context, config)

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.UNSUPPORTED_CONTEXT,)


def test_transaction_costs_can_eliminate_an_otherwise_positive_edge() -> None:
    configuration = MultiFactorConfiguration()
    prohibitive_costs = RoundTripCostEstimate(
        methodology_version_id=ConfigurationVersionId.parse("fixture-high-cost-v1"),
        entry_cost_return=Decimal("0.01"),
        exit_cost_return=Decimal("0.01"),
        spread_return=Decimal("0.01"),
        slippage_return=Decimal("0.01"),
    )
    decision = evaluate_strategy(
        evaluation_context(
            configuration,
            strategy_bars(["100"] * 59 + ["105"]),
            costs=prohibitive_costs,
        ),
        configuration,
    )

    assert isinstance(decision, NoTradeDecision)
    assert decision.reasons == (NoTradeReason.TRANSACTION_COST_CONCERN,)
    evidence = {item.name: item.value for item in decision.evidence}
    assert evidence["net_expected_return"] < Decimal(0)  # type: ignore[operator]
