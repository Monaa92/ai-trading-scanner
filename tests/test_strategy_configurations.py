from collections.abc import Callable
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ai_trading_scanner.domain import ModelId, StrategyId
from ai_trading_scanner.strategies import (
    BASELINE_RESEARCH_V1,
    BREAKOUT_STRATEGY_ID,
    MEAN_REVERSION_STRATEGY_ID,
    MOMENTUM_STRATEGY_ID,
    MULTI_FACTOR_STRATEGY_ID,
    REGISTERED_BASELINE_CONFIGURATIONS,
    BreakoutConfiguration,
    MomentumConfiguration,
    MultiFactorConfiguration,
    StrategyConfiguration,
    StrategyProfile,
    baseline_configuration,
    calculate_strategy_configuration_id,
)


def test_four_registered_baselines_have_stable_distinct_identity() -> None:
    assert tuple(config.profile for config in REGISTERED_BASELINE_CONFIGURATIONS) == tuple(
        StrategyProfile
    )
    assert {config.strategy_id for config in REGISTERED_BASELINE_CONFIGURATIONS} == {
        MOMENTUM_STRATEGY_ID,
        MEAN_REVERSION_STRATEGY_ID,
        BREAKOUT_STRATEGY_ID,
        MULTI_FACTOR_STRATEGY_ID,
    }
    assert all(
        config.baseline_name == BASELINE_RESEARCH_V1
        for config in REGISTERED_BASELINE_CONFIGURATIONS
    )
    assert (
        len(
            {
                calculate_strategy_configuration_id(config)
                for config in REGISTERED_BASELINE_CONFIGURATIONS
            }
        )
        == 4
    )


@pytest.mark.parametrize("configuration", REGISTERED_BASELINE_CONFIGURATIONS)
def test_baseline_lookup_returns_exact_registered_configuration(
    configuration: StrategyConfiguration,
) -> None:
    assert baseline_configuration(configuration.strategy_id) is configuration


def test_strategy_configuration_identity_changes_with_material_parameter() -> None:
    original = MomentumConfiguration()
    changed = MomentumConfiguration(pullback_lookback=6)

    assert calculate_strategy_configuration_id(original) != calculate_strategy_configuration_id(
        changed
    )


@pytest.mark.parametrize(
    ("configuration", "message"),
    [
        (lambda: MomentumConfiguration(ema_fast_period=20), "EMA periods"),
        (
            lambda: MomentumConfiguration(minimum_rsi=Decimal(90), maximum_rsi=Decimal(80)),
            "RSI bounds",
        ),
        (
            lambda: MultiFactorConfiguration(trend_weight=Decimal("0.31")),
            "sum exactly",
        ),
        (
            lambda: MultiFactorConfiguration(
                momentum_minimum_rsi=Decimal("90"),
                momentum_maximum_rsi=Decimal("80"),
            ),
            "RSI bounds",
        ),
        (lambda: BreakoutConfiguration(confirmation_bars=1), "greater than or equal to 2"),
        (lambda: MomentumConfiguration(proposal_validity_intervals=0), "greater than 0"),
        (
            lambda: MomentumConfiguration(minimum_expected_net_return=Decimal("Infinity")),
            "finite",
        ),
    ],
)
def test_invalid_strategy_parameters_fail_closed(
    configuration: Callable[[], StrategyConfiguration], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        configuration()


def test_float_strategy_parameters_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must not use float"):
        MomentumConfiguration(minimum_expected_net_return=0.01)  # type: ignore[arg-type]


def test_strategy_and_model_identities_remain_separate_types_and_content() -> None:
    strategy = StrategyId.parse("strategy:momentum-trend-following")
    model = ModelId.parse("model:example")
    dumped = MomentumConfiguration().model_dump(mode="json")

    assert type(strategy) is StrategyId
    assert type(model) is ModelId
    assert "model_id" not in dumped


def test_configuration_is_immutable_and_serializable() -> None:
    configuration = MomentumConfiguration()
    restored = MomentumConfiguration.model_validate_json(configuration.model_dump_json())

    assert restored == configuration
    with pytest.raises(ValidationError, match="frozen"):
        configuration.pullback_lookback = 7
