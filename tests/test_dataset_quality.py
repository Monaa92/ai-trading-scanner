from datetime import UTC, datetime, timedelta

import pytest

from ai_trading_scanner.market_data import (
    DatasetValidator,
    QualityCode,
    QualitySeverity,
    Timeframe,
    synthetic_regular_session_bars,
)


def test_valid_fixture_passes_with_exact_coverage() -> None:
    bars = synthetic_regular_session_bars()
    result = DatasetValidator().validate(
        bars,
        coverage_start_at=bars[0].start_at,
        coverage_end_at=bars[-1].end_at,
    )

    assert result.usable
    assert result.findings == ()


def test_missing_interval_is_reported_without_synthesizing_a_bar() -> None:
    bars = synthetic_regular_session_bars()
    result = DatasetValidator().validate(
        bars[:1],
        coverage_start_at=bars[0].start_at,
        coverage_end_at=bars[-1].end_at,
    )

    assert result.usable
    assert len(result.accepted_bars) == 1
    assert [finding.code for finding in result.findings] == [QualityCode.MISSING_INTERVAL]
    assert result.findings[0].severity is QualitySeverity.WARNING


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("high", "1", QualityCode.INVALID_OHLC),
        ("volume", "-1", QualityCode.INVALID_VOLUME),
        ("start_at", datetime(2024, 7, 2, 13, 30), QualityCode.TIMEZONE_PROBLEM),
    ],
)
def test_malformed_records_become_structured_fatal_findings(
    field: str, value: object, code: QualityCode
) -> None:
    raw = synthetic_regular_session_bars()[0].model_dump(mode="python")
    raw[field] = value

    result = DatasetValidator().validate([raw])

    assert not result.usable
    assert result.accepted_bars == ()
    assert result.findings[0].code is code
    assert result.findings[0].record_index == 0


def test_duplicate_and_out_of_order_records_are_fatal() -> None:
    first, second = synthetic_regular_session_bars()
    result = DatasetValidator().validate([second, first, first])
    codes = {finding.code for finding in result.findings}

    assert not result.usable
    assert QualityCode.OUT_OF_ORDER_OBSERVATION in codes
    assert QualityCode.DUPLICATE_OBSERVATION in codes


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("instrument_id", "XNYS:MSFT", QualityCode.INCONSISTENT_INSTRUMENT),
        ("timeframe", Timeframe.MINUTE_5, QualityCode.INCONSISTENT_TIMEFRAME),
    ],
)
def test_mixed_series_are_rejected(field: str, value: object, code: QualityCode) -> None:
    first, second = synthetic_regular_session_bars()
    raw = second.model_dump(mode="python")
    raw[field] = value
    if field == "timeframe":
        raw["end_at"] = raw["start_at"] + timedelta(minutes=5)
        raw["available_at"] = raw["end_at"] + timedelta(seconds=5)

    result = DatasetValidator().validate([first, raw])

    assert not result.usable
    assert code in {finding.code for finding in result.findings}


def test_bar_outside_regular_session_is_fatal() -> None:
    raw = synthetic_regular_session_bars()[0].model_dump(mode="python")
    raw["start_at"] = datetime(2024, 7, 6, 13, 30, tzinfo=UTC)
    raw["end_at"] = datetime(2024, 7, 6, 13, 31, tzinfo=UTC)
    raw["available_at"] = datetime(2024, 7, 6, 13, 31, 5, tzinfo=UTC)
    raw["ingested_at"] = datetime(2024, 7, 7, tzinfo=UTC)
    result = DatasetValidator().validate([raw])

    assert not result.usable
    assert result.findings[0].code is QualityCode.UNEXPECTED_SESSION_OBSERVATION


def test_mismatched_session_identity_is_fatal() -> None:
    raw = synthetic_regular_session_bars()[0].model_dump(mode="python")
    raw["session_id"] = "XNYS:2024-07-03:wrong-calendar"

    result = DatasetValidator().validate([raw])

    assert not result.usable
    assert result.findings[0].code is QualityCode.UNEXPECTED_SESSION_OBSERVATION


def test_excessive_availability_delay_is_visible_as_warning() -> None:
    bar = synthetic_regular_session_bars()[0]
    result = DatasetValidator().validate([bar], stale_after=timedelta(seconds=2))

    assert result.usable
    assert result.findings[0].code is QualityCode.STALE_OBSERVATION
