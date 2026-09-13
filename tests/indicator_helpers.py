"""Compact hand-auditable indicator test data."""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from ai_trading_scanner.domain import DatasetId, InstrumentId
from ai_trading_scanner.indicators.models import IndicatorPoint
from ai_trading_scanner.market_data import (
    AvailabilityMode,
    HistoricalBar,
    MarketDataSlice,
    QualityFinding,
    Timeframe,
    UsEquitiesCalendar,
)


def bars_for_session(
    session_date: date,
    closes: Sequence[str],
    *,
    highs: Sequence[str] | None = None,
    lows: Sequence[str] | None = None,
    volumes: Sequence[str] | None = None,
    minute_offsets: Sequence[int] | None = None,
) -> tuple[HistoricalBar, ...]:
    calendar = UsEquitiesCalendar()
    session = calendar.session_for_date(session_date)
    assert session is not None
    offsets = minute_offsets if minute_offsets is not None else range(len(closes))
    high_values = highs if highs is not None else closes
    low_values = lows if lows is not None else closes
    volume_values = volumes if volumes is not None else ["1"] * len(closes)
    assert len(closes) == len(high_values) == len(low_values) == len(volume_values)
    assert len(closes) == len(offsets)
    return tuple(
        HistoricalBar(
            instrument_id=InstrumentId.parse("XNYS:SYNTH"),
            session_id=session.session_id,
            timeframe=Timeframe.MINUTE_1,
            start_at=session.open_at + timedelta(minutes=offset),
            end_at=session.open_at + timedelta(minutes=offset + 1),
            open=Decimal(close),
            high=Decimal(high),
            low=Decimal(low),
            close=Decimal(close),
            volume=Decimal(volume),
            currency="USD",
            source_record_id=f"{session_date.isoformat()}-{offset}",
            received_at=None,
            available_at=session.open_at + timedelta(minutes=offset + 1, seconds=5),
            ingested_at=datetime(2024, 12, 31, tzinfo=UTC),
            availability_mode=AvailabilityMode.MODELED,
        )
        for offset, close, high, low, volume in zip(
            offsets, closes, high_values, low_values, volume_values, strict=True
        )
    )


def data_slice(
    bars: Sequence[HistoricalBar],
    *,
    findings: tuple[QualityFinding, ...] = (),
    as_of: datetime | None = None,
) -> MarketDataSlice:
    assert bars
    cutoff = as_of if as_of is not None else max(bar.available_at for bar in bars)
    return MarketDataSlice(
        dataset_id=DatasetId.parse("sha256:" + "a" * 64),
        as_of=cutoff,
        bars=tuple(bars),
        content_hash_sha256="b" * 64,
        quality_findings=findings,
    )


def values(points: Sequence[IndicatorPoint]) -> list[Decimal | None]:
    return [point.value for point in points]
