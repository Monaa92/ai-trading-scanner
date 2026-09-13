from datetime import date
from decimal import Decimal

from indicator_helpers import bars_for_session, data_slice, values

from ai_trading_scanner.indicators import ATRCalculator, ATRConfig, SmoothingMethod, calculate_atr


def config(period: int = 3) -> ATRConfig:
    return ATRConfig(period=period, smoothing=SmoothingMethod.WILDER)


def test_atr_true_range_seed_and_wilder_recurrence() -> None:
    bars = bars_for_session(
        date(2024, 7, 2),
        ["9", "12", "11", "15"],
        highs=["10", "13", "12", "16"],
        lows=["8", "11", "10", "14"],
    )

    result = calculate_atr(data_slice(bars), config())

    assert values(result.points) == [
        None,
        None,
        Decimal("2.666666666666666666666666666666667"),
        Decimal("3.444444444444444444444444444444443"),
    ]


def test_atr_captures_intra_session_gap_up_and_gap_down() -> None:
    bars = bars_for_session(
        date(2024, 7, 2),
        ["10", "15", "8"],
        highs=["11", "16", "9"],
        lows=["9", "14", "7"],
    )

    assert values(calculate_atr(data_slice(bars), config(period=1)).points) == [
        Decimal("2"),
        Decimal("6"),
        Decimal("8"),
    ]


def test_atr_flat_bars_are_zero() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["5", "5"])

    assert values(calculate_atr(data_slice(bars), config(period=1)).points) == [
        Decimal("0"),
        Decimal("0"),
    ]


def test_v1_atr_resets_session_and_excludes_overnight_gap() -> None:
    first = bars_for_session(date(2024, 7, 5), ["10"], highs=["11"], lows=["9"])
    after_weekend = bars_for_session(date(2024, 7, 8), ["20"], highs=["21"], lows=["19"])

    result = calculate_atr(data_slice(first + after_weekend), config(period=1))

    assert values(result.points) == [Decimal("2"), Decimal("2")]


def test_atr_restarts_after_missing_interval() -> None:
    bars = bars_for_session(
        date(2024, 7, 2),
        ["10", "12", "20", "22"],
        highs=["11", "13", "21", "23"],
        lows=["9", "11", "19", "21"],
        minute_offsets=[0, 1, 3, 4],
    )

    result = calculate_atr(data_slice(bars), config(period=2))

    assert values(result.points) == [None, Decimal("2.5"), None, Decimal("2.5")]
    assert result.points[2].reason.value == "MISSING_INTERVAL"


def test_atr_batch_and_incremental_results_match() -> None:
    bars = bars_for_session(
        date(2024, 7, 2), ["10", "11", "10"], highs=["11", "12", "11"], lows=["9", "10", "9"]
    )
    configuration = config(period=2)

    calculator = ATRCalculator(configuration)
    assert calculate_atr(data_slice(bars), configuration).points == tuple(
        calculator.update(bar) for bar in bars
    )
