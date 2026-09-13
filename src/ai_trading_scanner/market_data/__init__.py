"""Historical market-data foundation public API."""

from ai_trading_scanner.market_data.calendar import TradingSession, UsEquitiesCalendar
from ai_trading_scanner.market_data.dataset import (
    CanonicalDataset,
    CausalBarReader,
    MarketDataSlice,
    calculate_dataset_id,
)
from ai_trading_scanner.market_data.fixtures import (
    synthetic_regular_session_bars,
    validate_offline_fixture,
)
from ai_trading_scanner.market_data.models import (
    AdjustmentMethod,
    AssetClass,
    AvailabilityMode,
    DataProvenance,
    HistoricalBar,
    Instrument,
    MissingInterval,
    QualityStatus,
    Timeframe,
)
from ai_trading_scanner.market_data.quality import (
    DatasetValidationResult,
    DatasetValidator,
    QualityCode,
    QualityFinding,
    QualitySeverity,
)

__all__ = [
    "AdjustmentMethod",
    "AssetClass",
    "AvailabilityMode",
    "CanonicalDataset",
    "CausalBarReader",
    "DataProvenance",
    "DatasetValidationResult",
    "DatasetValidator",
    "HistoricalBar",
    "Instrument",
    "MarketDataSlice",
    "MissingInterval",
    "QualityCode",
    "QualityFinding",
    "QualitySeverity",
    "QualityStatus",
    "Timeframe",
    "TradingSession",
    "UsEquitiesCalendar",
    "calculate_dataset_id",
    "synthetic_regular_session_bars",
    "validate_offline_fixture",
]
