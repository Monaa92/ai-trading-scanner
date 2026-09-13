"""XNYS regular-session calendar boundary backed by local reference data."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from importlib.metadata import version
from typing import Final
from zoneinfo import ZoneInfo

import exchange_calendars as exchange_calendars  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from ai_trading_scanner.market_data.models import Timeframe

_MARKET_TIMEZONE: Final = "America/New_York"


class TradingSession(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_date: date
    session_id: str
    open_at: datetime
    close_at: datetime
    market_timezone: str
    calendar_name: str
    calendar_version: str
    early_close: bool


class UsEquitiesCalendar:
    """Small project-owned API over the version-pinned XNYS calendar."""

    name = "XNYS"
    market_timezone = _MARKET_TIMEZONE

    def __init__(self) -> None:
        self._calendar = exchange_calendars.get_calendar(self.name)
        self.version = f"exchange-calendars-{version('exchange-calendars')}"

    def session_for_date(self, session_date: date) -> TradingSession | None:
        label = session_date.isoformat()
        if not self._calendar.is_session(label):
            return None
        open_at = self._calendar.session_open(label).to_pydatetime().astimezone(UTC)
        close_at = self._calendar.session_close(label).to_pydatetime().astimezone(UTC)
        local_close = close_at.astimezone(ZoneInfo(self.market_timezone))
        return TradingSession(
            session_date=session_date,
            session_id=f"{self.name}:{session_date.isoformat()}:{self.version}",
            open_at=open_at,
            close_at=close_at,
            market_timezone=self.market_timezone,
            calendar_name=self.name,
            calendar_version=self.version,
            early_close=local_close.time() < time(16, 0),
        )

    def is_open_at(self, timestamp: datetime) -> bool:
        timestamp = self._require_aware(timestamp)
        local_date = timestamp.astimezone(ZoneInfo(self.market_timezone)).date()
        session = self.session_for_date(local_date)
        return session is not None and session.open_at <= timestamp < session.close_at

    def contains_interval(self, start_at: datetime, end_at: datetime) -> bool:
        start_at = self._require_aware(start_at)
        end_at = self._require_aware(end_at)
        local_date = start_at.astimezone(ZoneInfo(self.market_timezone)).date()
        session = self.session_for_date(local_date)
        return (
            session is not None
            and session.open_at <= start_at
            and start_at < end_at <= session.close_at
        )

    def expected_intervals(
        self, start_at: datetime, end_at: datetime, timeframe: Timeframe
    ) -> tuple[tuple[datetime, datetime], ...]:
        start_at = self._require_aware(start_at)
        end_at = self._require_aware(end_at)
        if end_at <= start_at:
            raise ValueError("coverage end must follow start")
        market_tz = ZoneInfo(self.market_timezone)
        first_date = start_at.astimezone(market_tz).date()
        last_date = (end_at - timedelta(microseconds=1)).astimezone(market_tz).date()
        intervals: list[tuple[datetime, datetime]] = []
        current_date = first_date
        while current_date <= last_date:
            session = self.session_for_date(current_date)
            if session is not None:
                cursor = session.open_at
                while cursor + timeframe.duration <= session.close_at:
                    interval_end = cursor + timeframe.duration
                    if cursor >= start_at and interval_end <= end_at:
                        intervals.append((cursor, interval_end))
                    cursor = interval_end
            current_date += timedelta(days=1)
        return tuple(intervals)

    @staticmethod
    def _require_aware(timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return timestamp.astimezone(UTC)
