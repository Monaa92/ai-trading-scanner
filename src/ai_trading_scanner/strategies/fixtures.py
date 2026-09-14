"""Fast credential-free validation of the registered strategy contract set."""

from ai_trading_scanner.strategies.configurations import (
    REGISTERED_BASELINE_CONFIGURATIONS,
    StrategyProfile,
    calculate_strategy_configuration_id,
)


def validate_offline_strategy_fixture() -> bool:
    configurations = REGISTERED_BASELINE_CONFIGURATIONS
    return (
        tuple(configuration.profile for configuration in configurations) == tuple(StrategyProfile)
        and len({configuration.strategy_id for configuration in configurations}) == 4
        and len(
            {calculate_strategy_configuration_id(configuration) for configuration in configurations}
        )
        == 4
    )
