from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, getcontext

import pytest
from indicator_helpers import bars_for_session, data_slice

from ai_trading_scanner.indicators import (
    ATRConfig,
    EMAConfig,
    IndicatorSeries,
    PriceBasis,
    ResetPolicy,
    RSIConfig,
    SmoothingMethod,
    VWAPConfig,
    calculate_atr,
    calculate_ema,
    calculate_rsi,
    calculate_vwap,
)
from ai_trading_scanner.market_data import (
    AdjustmentMethod,
    AvailabilityMode,
    CanonicalDataset,
    CausalBarReader,
    DataProvenance,
    MarketDataSlice,
    MissingInterval,
    QualityCode,
    QualityStatus,
    Timeframe,
)


def calculations() -> tuple[Callable[[MarketDataSlice], IndicatorSeries], ...]:
    return (
        lambda data: calculate_ema(data, EMAConfig(period=3)),
        lambda data: calculate_rsi(data, RSIConfig(period=3, smoothing=SmoothingMethod.WILDER)),
        lambda data: calculate_atr(data, ATRConfig(period=3, smoothing=SmoothingMethod.WILDER)),
        lambda data: calculate_vwap(
            data,
            VWAPConfig(
                price_basis=PriceBasis.TYPICAL_PRICE,
                reset_policy=ResetPolicy.SESSION,
            ),
        ),
    )


@pytest.mark.parametrize("calculate", calculations())
def test_every_indicator_is_prefix_invariant(
    calculate: Callable[[MarketDataSlice], IndicatorSeries],
) -> None:
    bars = bars_for_session(
        date(2024, 7, 2),
        ["10", "11", "10", "13", "12", "15"],
        highs=["11", "12", "11", "14", "13", "16"],
        lows=["9", "10", "9", "12", "11", "14"],
        volumes=["1", "2", "3", "4", "5", "6"],
    )
    full = calculate(data_slice(bars)).points

    for length in (1, 2, 3, 4, 6):
        prefix = calculate(data_slice(bars[:length])).points
        assert prefix == full[:length]


def provenance(
    *, quality_status: QualityStatus = QualityStatus.PASS, missing: tuple[MissingInterval, ...] = ()
) -> DataProvenance:
    return DataProvenance(
        provider="synthetic-test",
        timeframe=Timeframe.MINUTE_1,
        source_timezone="America/New_York",
        covered_start_at=datetime(2024, 7, 2, 13, 30, tzinfo=UTC),
        covered_end_at=datetime(2024, 7, 2, 13, 33, tzinfo=UTC),
        ingested_at=datetime(2024, 12, 31, tzinfo=UTC),
        adjustment_method=AdjustmentMethod.RAW,
        availability_mode=AvailabilityMode.MODELED,
        modeled_publication_delay_seconds=5,
        calendar_version="exchange-calendars-4.13.2",
        normalization_version="normalizer-v1",
        quality_status=quality_status,
        missing_intervals=missing,
    )


def test_indicator_consumes_only_bars_visible_in_causal_slice() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["1", "2", "100"])
    dataset = CanonicalDataset.create(provenance(), bars)
    reader = CausalBarReader(dataset)
    earlier = reader.slice_as_of(bars[1].available_at)
    later = reader.slice_as_of(bars[2].available_at)

    early_result = calculate_ema(earlier, EMAConfig(period=2))
    late_result = calculate_ema(later, EMAConfig(period=2))

    assert early_result.points == late_result.points[:2]
    assert early_result.points[-1].value == Decimal("1.5")


def test_future_bar_in_forged_slice_fails_closed() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["1", "2"])
    forged = data_slice(bars, as_of=bars[0].available_at)

    with pytest.raises(ValueError, match="unavailable"):
        calculate_ema(forged, EMAConfig(period=1))


@pytest.mark.parametrize("mutation", ["duplicate", "out_of_order"])
def test_fatal_sequence_quality_fails_closed(mutation: str) -> None:
    first, second = bars_for_session(date(2024, 7, 2), ["1", "2"])
    bars = (first, first) if mutation == "duplicate" else (second, first)

    with pytest.raises(ValueError, match="fatal quality"):
        calculate_ema(data_slice(bars), EMAConfig(period=1))


def test_missing_interval_warning_survives_causal_slice_and_indicator_output() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["1", "3"], minute_offsets=[0, 2])
    missing = MissingInterval(
        start_at=bars[0].end_at,
        end_at=bars[1].start_at,
        reason="synthetic missing bar",
    )
    dataset = CanonicalDataset.create(
        provenance(quality_status=QualityStatus.WARN, missing=(missing,)), bars
    )
    data = CausalBarReader(dataset).slice_as_of(bars[-1].available_at)

    result = calculate_ema(data, EMAConfig(period=1))

    assert [finding.code for finding in result.quality_findings] == [QualityCode.MISSING_INTERVAL]
    assert len(result.points) == 2
    assert result.points[-1].value == Decimal("3")


def test_future_missing_interval_warning_is_not_exposed_early() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["1", "3"], minute_offsets=[0, 2])
    missing = MissingInterval(start_at=bars[0].end_at, end_at=bars[1].start_at)
    dataset = CanonicalDataset.create(
        provenance(quality_status=QualityStatus.WARN, missing=(missing,)), bars
    )

    data = CausalBarReader(dataset).slice_as_of(bars[0].available_at)

    assert data.quality_findings == ()

    before_modeled_deadline = CausalBarReader(dataset).slice_as_of(
        missing.end_at + timedelta(seconds=4)
    )
    at_modeled_deadline = CausalBarReader(dataset).slice_as_of(
        missing.end_at + timedelta(seconds=5)
    )
    assert before_modeled_deadline.quality_findings == ()
    assert [finding.code for finding in at_modeled_deadline.quality_findings] == [
        QualityCode.MISSING_INTERVAL
    ]


def test_decimal_results_ignore_process_global_precision() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["1", "2", "4", "8", "16"])
    original_precision = getcontext().prec
    try:
        getcontext().prec = 6
        low_global_precision = calculate_rsi(
            data_slice(bars), RSIConfig(period=3, smoothing=SmoothingMethod.WILDER)
        )
        getcontext().prec = 50
        high_global_precision = calculate_rsi(
            data_slice(bars), RSIConfig(period=3, smoothing=SmoothingMethod.WILDER)
        )
    finally:
        getcontext().prec = original_precision

    assert low_global_precision.points == high_global_precision.points


def test_empty_slice_is_rejected_without_numeric_placeholder() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["1"])
    empty = data_slice(bars).model_copy(update={"bars": ()})

    with pytest.raises(ValueError, match="at least one"):
        calculate_ema(empty, EMAConfig(period=1))


def test_mixed_currency_price_units_fail_closed() -> None:
    bars = bars_for_session(date(2024, 7, 2), ["1", "2"])
    mixed = bars[1].model_copy(update={"currency": "EUR"})

    with pytest.raises(ValueError, match="currency"):
        calculate_ema(data_slice((bars[0], mixed)), EMAConfig(period=1))
