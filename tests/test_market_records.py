from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ai_trading_scanner.domain import InstrumentId
from ai_trading_scanner.market_data import (
    AdjustmentMethod,
    AvailabilityMode,
    DataProvenance,
    HistoricalBar,
    Timeframe,
)


def valid_bar(**changes: object) -> HistoricalBar:
    values: dict[str, object] = {
        "instrument_id": InstrumentId.parse("XNYS:AAPL"),
        "session_id": "XNYS:2024-07-02:exchange-calendars-4.13.2",
        "timeframe": Timeframe.MINUTE_1,
        "start_at": datetime(2024, 7, 2, 13, 30, tzinfo=UTC),
        "end_at": datetime(2024, 7, 2, 13, 31, tzinfo=UTC),
        "open": "100.00",
        "high": "101.00",
        "low": "99.50",
        "close": "100.50",
        "volume": "1500",
        "currency": "USD",
        "source_record_id": "provider-1",
        "received_at": datetime(2024, 7, 2, 13, 31, 1, tzinfo=UTC),
        "available_at": datetime(2024, 7, 2, 13, 31, 2, tzinfo=UTC),
        "ingested_at": datetime(2024, 7, 6, tzinfo=UTC),
        "availability_mode": AvailabilityMode.ACTUAL,
    }
    values.update(changes)
    return HistoricalBar.model_validate(values)


def test_bar_uses_half_open_interval_and_normalizes_aware_times_to_utc() -> None:
    eastern = timezone(timedelta(hours=-4))
    bar = valid_bar(
        start_at=datetime(2024, 7, 2, 9, 30, tzinfo=eastern),
        end_at=datetime(2024, 7, 2, 9, 31, tzinfo=eastern),
    )

    assert bar.start_at == datetime(2024, 7, 2, 13, 30, tzinfo=UTC)
    assert bar.event_at == bar.end_at
    assert bar.model_config["frozen"] is True


def test_validated_bar_is_immutable() -> None:
    bar = valid_bar()

    with pytest.raises(ValidationError, match="frozen"):
        bar.close = Decimal("101.00")


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"start_at": datetime(2024, 7, 2, 13, 30)}, "timezone-aware"),
        ({"high": "99.00"}, "OHLC"),
        ({"volume": "-1"}, "volume"),
        ({"open": 100.0}, "not float"),
        ({"end_at": datetime(2024, 7, 2, 13, 35, tzinfo=UTC)}, "timeframe"),
        (
            {"available_at": datetime(2024, 7, 2, 13, 30, 59, tzinfo=UTC)},
            "interval ends",
        ),
        ({"received_at": None}, "requires received_at"),
        (
            {"ingested_at": datetime(2024, 7, 2, 13, 31, 1, tzinfo=UTC)},
            "ingested_at",
        ),
    ],
)
def test_invalid_canonical_bars_fail_closed(changes: dict[str, object], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        valid_bar(**changes)


def test_historical_provenance_requires_explicit_availability_model() -> None:
    base: dict[str, object] = {
        "provider": "synthetic-test",
        "timeframe": "1m",
        "source_timezone": "America/New_York",
        "ingested_at": datetime(2024, 7, 6, tzinfo=UTC),
        "adjustment_method": AdjustmentMethod.RAW,
        "availability_mode": AvailabilityMode.MODELED,
        "calendar_version": "exchange-calendars-4.13.2",
        "normalization_version": "normalizer-v1",
    }
    with pytest.raises(ValidationError, match="explicit publication delay"):
        DataProvenance.model_validate(base)

    base["modeled_publication_delay_seconds"] = 5
    provenance = DataProvenance.model_validate(base)

    assert provenance.modeled_publication_delay_seconds == 5
    assert provenance.source_dataset_id is None


def test_unknown_or_provider_defined_adjustment_details_are_not_fabricated() -> None:
    with pytest.raises(ValidationError, match="adjustment_details"):
        DataProvenance(
            provider="provider",
            timeframe=Timeframe.MINUTE_1,
            source_timezone="UTC",
            ingested_at=datetime(2024, 7, 6, tzinfo=UTC),
            adjustment_method=AdjustmentMethod.PROVIDER_DEFINED,
            availability_mode=AvailabilityMode.MODELED,
            modeled_publication_delay_seconds=0,
            calendar_version="calendar-v1",
            normalization_version="normalizer-v1",
        )


def test_decimal_values_are_preserved_without_binary_float_rounding() -> None:
    bar = valid_bar(close="100.123400")
    assert bar.close == Decimal("100.123400")
