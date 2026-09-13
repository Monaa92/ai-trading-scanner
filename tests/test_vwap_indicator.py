from datetime import date
from decimal import Decimal

from indicator_helpers import bars_for_session, data_slice, values

from ai_trading_scanner.indicators import (
    PriceBasis,
    ResetPolicy,
    VWAPCalculator,
    VWAPConfig,
    calculate_vwap,
)


def config() -> VWAPConfig:
    return VWAPConfig(
        price_basis=PriceBasis.TYPICAL_PRICE,
        reset_policy=ResetPolicy.SESSION,
    )


def test_vwap_uses_typical_price_and_cumulative_volume() -> None:
    bars = bars_for_session(
        date(2024, 7, 2),
        ["2", "5"],
        highs=["3", "6"],
        lows=["1", "4"],
        volumes=["1", "3"],
    )

    result = calculate_vwap(data_slice(bars), config())

    assert values(result.points) == [Decimal("2"), Decimal("4.25")]


def test_vwap_zero_volume_is_unavailable_until_positive_volume() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["2", "5", "8"], volumes=["0", "0", "2"])

    result = calculate_vwap(data_slice(bars), config())

    assert values(result.points) == [None, None, Decimal("8")]
    assert result.points[0].reason.value == "ZERO_CUMULATIVE_VOLUME"
    assert result.points[1].reason.value == "ZERO_CUMULATIVE_VOLUME"


def test_vwap_resets_after_early_close_holiday_and_weekend() -> None:
    early_close = bars_for_session(date(2024, 7, 3), ["2", "4"])
    after_holiday = bars_for_session(date(2024, 7, 5), ["10"])
    after_weekend = bars_for_session(date(2024, 7, 8), ["20"])

    result = calculate_vwap(data_slice(early_close + after_holiday + after_weekend), config())

    assert values(result.points) == [Decimal("2"), Decimal("3"), Decimal("10"), Decimal("20")]


def test_vwap_reset_is_independent_of_dst_utc_open_change() -> None:
    before_dst = bars_for_session(date(2024, 3, 8), ["2"])
    after_dst = bars_for_session(date(2024, 3, 11), ["9"])

    result = calculate_vwap(data_slice(before_dst + after_dst), config())

    assert values(result.points) == [Decimal("2"), Decimal("9")]
    assert before_dst[0].start_at.hour == 14
    assert after_dst[0].start_at.hour == 13


def test_vwap_never_labels_partial_or_gapped_prefix_as_session_vwap() -> None:
    partial = bars_for_session(date(2024, 7, 2), ["2", "4"], minute_offsets=[1, 2])
    gapped = bars_for_session(date(2024, 7, 3), ["10", "12", "14"], minute_offsets=[0, 2, 3])

    result = calculate_vwap(data_slice(partial + gapped), config())

    assert values(result.points) == [None, None, Decimal("10"), None, None]
    assert result.points[0].reason.value == "INCOMPLETE_SESSION_PREFIX"
    assert result.points[3].reason.value == "MISSING_INTERVAL"
    assert result.points[4].reason.value == "INCOMPLETE_SESSION_PREFIX"


def test_vwap_batch_and_incremental_results_match() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["1", "2", "3"], volumes=["1", "2", "3"])
    configuration = config()

    calculator = VWAPCalculator(configuration)
    assert calculate_vwap(data_slice(bars), configuration).points == tuple(
        calculator.update(bar) for bar in bars
    )
