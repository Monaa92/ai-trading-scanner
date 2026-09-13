from datetime import date
from decimal import Decimal

import pytest
from indicator_helpers import bars_for_session, data_slice, values

from ai_trading_scanner.indicators import RSICalculator, RSIConfig, SmoothingMethod, calculate_rsi


def config(period: int = 3) -> RSIConfig:
    return RSIConfig(period=period, smoothing=SmoothingMethod.WILDER)


@pytest.mark.parametrize(
    ("closes", "expected"),
    [
        (["1", "2", "3", "4"], Decimal("100")),
        (["4", "3", "2", "1"], Decimal("0")),
        (["2", "2", "2", "2"], Decimal("50")),
        (["1", "2", "1", "2"], Decimal("66.66666666666666666666666666666667")),
    ],
)
def test_rsi_wilder_seed_and_zero_denominator_conventions(
    closes: list[str], expected: Decimal
) -> None:
    bars = bars_for_session(date(2024, 7, 2), closes)

    result = calculate_rsi(data_slice(bars), config())

    assert values(result.points[:-1]) == [None, None, None]
    assert result.points[-1].value == expected
    assert result.unit.value == "PERCENT"


def test_rsi_wilder_recurrence_is_exact() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["1", "2", "1", "2", "1"])

    result = calculate_rsi(data_slice(bars), config())

    assert result.points[-1].value == Decimal("44.44444444444444444444444444444444")


def test_rsi_resets_each_session_and_rewarms_after_gap() -> None:
    first = bars_for_session(date(2024, 7, 2), ["1", "2", "3"])
    second = bars_for_session(date(2024, 7, 3), ["10", "11", "12"])
    gapped = bars_for_session(
        date(2024, 7, 5), ["20", "21", "30", "31"], minute_offsets=[0, 1, 3, 4]
    )

    result = calculate_rsi(data_slice(first + second + gapped), config(period=2))

    assert values(result.points) == [
        None,
        None,
        Decimal("100"),
        None,
        None,
        Decimal("100"),
        None,
        None,
        None,
        None,
    ]
    assert result.points[-1].reason.value == "MISSING_INTERVAL"


def test_rsi_batch_and_incremental_results_match() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["1", "2", "1", "3", "2"])
    configuration = config(period=2)

    calculator = RSICalculator(configuration)
    assert calculate_rsi(data_slice(bars), configuration).points == tuple(
        calculator.update(bar) for bar in bars
    )
