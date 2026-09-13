from datetime import date
from decimal import Decimal

import pytest
from indicator_helpers import bars_for_session, data_slice, values

from ai_trading_scanner.indicators import EMACalculator, EMAConfig, calculate_ema


@pytest.mark.parametrize(
    ("closes", "expected"),
    [
        (["5", "5", "5", "5"], [None, None, Decimal("5"), Decimal("5")]),
        (["1", "2", "3", "4"], [None, None, Decimal("2"), Decimal("3")]),
        (["4", "3", "2", "1"], [None, None, Decimal("3"), Decimal("2")]),
    ],
)
def test_ema_uses_sma_seed_and_exact_recurrence(
    closes: list[str], expected: list[Decimal | None]
) -> None:
    bars = bars_for_session(date(2024, 7, 2), closes)

    result = calculate_ema(data_slice(bars), EMAConfig(period=3))

    assert values(result.points) == expected
    assert [point.ready for point in result.points] == [value is not None for value in expected]


def test_ema_period_one_is_ready_on_first_bar() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["1.1", "2.2"])

    assert values(calculate_ema(data_slice(bars), EMAConfig(period=1)).points) == [
        Decimal("1.1"),
        Decimal("2.2"),
    ]


def test_ema_resets_at_session_boundary_and_after_missing_interval() -> None:
    first = bars_for_session(date(2024, 7, 2), ["1", "3"])
    second = bars_for_session(date(2024, 7, 3), ["10"])
    gapped = bars_for_session(
        date(2024, 7, 5), ["20", "22", "30", "32"], minute_offsets=[0, 1, 3, 4]
    )

    result = calculate_ema(data_slice(first + second + gapped), EMAConfig(period=2))

    assert values(result.points) == [
        None,
        Decimal("2"),
        None,
        None,
        Decimal("21"),
        None,
        Decimal("31"),
    ]
    assert result.points[5].reason.value == "MISSING_INTERVAL"


def test_ema_batch_and_incremental_results_match() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["1", "2", "4", "8"])
    configuration = EMAConfig(period=2)

    batch = calculate_ema(data_slice(bars), configuration)
    calculator = EMACalculator(configuration)
    incremental = tuple(calculator.update(bar) for bar in bars)

    assert batch.points == incremental
