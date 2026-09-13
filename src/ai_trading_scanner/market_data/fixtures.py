"""Small deterministic synthetic fixtures for offline validation."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ai_trading_scanner.domain import InstrumentId
from ai_trading_scanner.market_data.calendar import UsEquitiesCalendar
from ai_trading_scanner.market_data.models import AvailabilityMode, HistoricalBar, Timeframe
from ai_trading_scanner.market_data.quality import DatasetValidator


def synthetic_regular_session_bars() -> tuple[HistoricalBar, ...]:
    first_start = datetime(2024, 7, 2, 13, 30, tzinfo=UTC)
    session = UsEquitiesCalendar().session_for_date(first_start.date())
    assert session is not None
    return tuple(
        HistoricalBar(
            instrument_id=InstrumentId.parse("XNYS:SYNTH"),
            session_id=session.session_id,
            timeframe=Timeframe.MINUTE_1,
            start_at=first_start + timedelta(minutes=index),
            end_at=first_start + timedelta(minutes=index + 1),
            open=Decimal("100.00") + index,
            high=Decimal("100.20") + index,
            low=Decimal("99.90") + index,
            close=Decimal("100.10") + index,
            volume=Decimal("1000") + index,
            currency="USD",
            source_record_id=f"synthetic-{index}",
            received_at=None,
            available_at=first_start + timedelta(minutes=index + 1, seconds=5),
            ingested_at=datetime(2024, 7, 6, tzinfo=UTC),
            availability_mode=AvailabilityMode.MODELED,
        )
        for index in range(2)
    )


def validate_offline_fixture() -> bool:
    bars = synthetic_regular_session_bars()
    result = DatasetValidator(UsEquitiesCalendar()).validate(
        bars,
        coverage_start_at=bars[0].start_at,
        coverage_end_at=bars[-1].end_at,
    )
    return result.usable and not result.findings
