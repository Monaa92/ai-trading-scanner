"""Small deterministic indicator fixture for offline health reporting."""

from datetime import UTC, datetime
from decimal import Decimal

from ai_trading_scanner.indicators.calculators import (
    calculate_atr,
    calculate_ema,
    calculate_rsi,
    calculate_vwap,
)
from ai_trading_scanner.indicators.models import (
    ATRConfig,
    EMAConfig,
    PriceBasis,
    ResetPolicy,
    RSIConfig,
    SmoothingMethod,
    VWAPConfig,
)
from ai_trading_scanner.market_data import (
    AdjustmentMethod,
    AvailabilityMode,
    CanonicalDataset,
    CausalBarReader,
    DataProvenance,
    QualityStatus,
    Timeframe,
    synthetic_regular_session_bars,
)


def validate_offline_indicator_fixture() -> bool:
    bars = synthetic_regular_session_bars()
    provenance = DataProvenance(
        provider="synthetic-health",
        timeframe=Timeframe.MINUTE_1,
        source_timezone="America/New_York",
        ingested_at=datetime(2024, 7, 6, tzinfo=UTC),
        adjustment_method=AdjustmentMethod.RAW,
        availability_mode=AvailabilityMode.MODELED,
        modeled_publication_delay_seconds=5,
        calendar_version="exchange-calendars-4.13.2",
        normalization_version="normalizer-v1",
        quality_status=QualityStatus.PASS,
    )
    data = CausalBarReader(CanonicalDataset.create(provenance, bars)).slice_as_of(
        bars[-1].available_at
    )
    ema = calculate_ema(data, EMAConfig(period=2)).points[-1]
    rsi = calculate_rsi(data, RSIConfig(period=1, smoothing=SmoothingMethod.WILDER)).points[-1]
    atr = calculate_atr(data, ATRConfig(period=2, smoothing=SmoothingMethod.WILDER)).points[-1]
    vwap = calculate_vwap(
        data,
        VWAPConfig(
            price_basis=PriceBasis.TYPICAL_PRICE,
            reset_policy=ResetPolicy.SESSION,
        ),
    ).points[-1]
    return (
        ema.value == Decimal("100.60")
        and rsi.value == Decimal("100")
        and atr.value == Decimal("0.70")
        and vwap.ready
    )
