from datetime import UTC, date, datetime

import pytest

from ai_trading_scanner.market_data import Timeframe, UsEquitiesCalendar


@pytest.fixture(scope="module")
def calendar() -> UsEquitiesCalendar:
    return UsEquitiesCalendar()


def test_regular_session_respects_dst_and_half_open_close(
    calendar: UsEquitiesCalendar,
) -> None:
    winter = calendar.session_for_date(date(2024, 1, 3))
    summer = calendar.session_for_date(date(2024, 7, 2))
    assert winter is not None and summer is not None

    assert winter.open_at == datetime(2024, 1, 3, 14, 30, tzinfo=UTC)
    assert summer.open_at == datetime(2024, 7, 2, 13, 30, tzinfo=UTC)
    assert calendar.is_open_at(summer.open_at)
    assert not calendar.is_open_at(datetime(2024, 7, 2, 13, 29, 59, tzinfo=UTC))
    assert not calendar.is_open_at(summer.close_at)
    assert not calendar.is_open_at(datetime(2024, 7, 2, 20, 0, 1, tzinfo=UTC))
    assert summer.session_id.startswith("XNYS:2024-07-02:exchange-calendars-")


def test_weekends_and_us_market_holidays_are_not_sessions(
    calendar: UsEquitiesCalendar,
) -> None:
    assert calendar.session_for_date(date(2024, 7, 4)) is None
    assert calendar.session_for_date(date(2024, 7, 6)) is None


def test_early_close_is_explicit(calendar: UsEquitiesCalendar) -> None:
    session = calendar.session_for_date(date(2024, 7, 3))
    assert session is not None
    assert session.early_close is True
    assert session.close_at == datetime(2024, 7, 3, 17, 0, tzinfo=UTC)


def test_expected_intervals_do_not_invent_weekend_or_holiday_bars(
    calendar: UsEquitiesCalendar,
) -> None:
    intervals = calendar.expected_intervals(
        datetime(2024, 7, 3, 16, 59, tzinfo=UTC),
        datetime(2024, 7, 5, 13, 31, tzinfo=UTC),
        Timeframe.MINUTE_1,
    )

    assert intervals == (
        (
            datetime(2024, 7, 3, 16, 59, tzinfo=UTC),
            datetime(2024, 7, 3, 17, 0, tzinfo=UTC),
        ),
        (
            datetime(2024, 7, 5, 13, 30, tzinfo=UTC),
            datetime(2024, 7, 5, 13, 31, tzinfo=UTC),
        ),
    )


def test_naive_calendar_timestamp_is_rejected(calendar: UsEquitiesCalendar) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        calendar.is_open_at(datetime(2024, 7, 2, 13, 30))
