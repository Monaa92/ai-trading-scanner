"""Structured market-data validation with fail-closed findings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, ValidationError

from ai_trading_scanner.market_data.calendar import UsEquitiesCalendar
from ai_trading_scanner.market_data.models import HistoricalBar, Timeframe


class QualitySeverity(StrEnum):
    WARNING = "WARNING"
    FATAL = "FATAL"


class QualityCode(StrEnum):
    MISSING_INTERVAL = "MISSING_INTERVAL"
    DUPLICATE_OBSERVATION = "DUPLICATE_OBSERVATION"
    OUT_OF_ORDER_OBSERVATION = "OUT_OF_ORDER_OBSERVATION"
    INVALID_OHLC = "INVALID_OHLC"
    INVALID_VOLUME = "INVALID_VOLUME"
    TIMEZONE_PROBLEM = "TIMEZONE_PROBLEM"
    UNEXPECTED_SESSION_OBSERVATION = "UNEXPECTED_SESSION_OBSERVATION"
    STALE_OBSERVATION = "STALE_OBSERVATION"
    INCONSISTENT_INSTRUMENT = "INCONSISTENT_INSTRUMENT"
    INCONSISTENT_TIMEFRAME = "INCONSISTENT_TIMEFRAME"
    MALFORMED_RECORD = "MALFORMED_RECORD"


class QualityFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: QualityCode
    severity: QualitySeverity
    message: str
    record_index: int | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


class DatasetValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    accepted_bars: tuple[HistoricalBar, ...]
    findings: tuple[QualityFinding, ...]

    @property
    def usable(self) -> bool:
        return all(finding.severity is not QualitySeverity.FATAL for finding in self.findings)


def _validation_code(error: ValidationError) -> QualityCode:
    details = " ".join(
        f"{'/'.join(str(part) for part in item['loc'])} {item['msg']}" for item in error.errors()
    ).lower()
    if "timezone" in details or "timezone-aware" in details:
        return QualityCode.TIMEZONE_PROBLEM
    if "volume" in details:
        return QualityCode.INVALID_VOLUME
    if any(term in details for term in ("ohlc", "open", "high", "low", "close", "price")):
        return QualityCode.INVALID_OHLC
    return QualityCode.MALFORMED_RECORD


class DatasetValidator:
    def __init__(self, calendar: UsEquitiesCalendar | None = None) -> None:
        self._calendar = calendar if calendar is not None else UsEquitiesCalendar()

    def validate(
        self,
        records: Sequence[HistoricalBar | Mapping[str, Any]],
        *,
        coverage_start_at: datetime | None = None,
        coverage_end_at: datetime | None = None,
        stale_after: timedelta | None = None,
    ) -> DatasetValidationResult:
        bars: list[HistoricalBar] = []
        findings: list[QualityFinding] = []
        for index, record in enumerate(records):
            try:
                bar = (
                    record
                    if isinstance(record, HistoricalBar)
                    else HistoricalBar.model_validate(record)
                )
            except ValidationError as exc:
                findings.append(
                    QualityFinding(
                        code=_validation_code(exc),
                        severity=QualitySeverity.FATAL,
                        message="record failed canonical schema validation",
                        record_index=index,
                    )
                )
                continue
            bars.append(bar)

        seen: set[tuple[str, Timeframe, datetime]] = set()
        previous_key: tuple[str, Timeframe, datetime] | None = None
        expected_instrument = bars[0].instrument_id if bars else None
        expected_timeframe = bars[0].timeframe if bars else None
        for index, bar in enumerate(bars):
            key = (str(bar.instrument_id), bar.timeframe, bar.start_at)
            if key in seen:
                findings.append(self._fatal(QualityCode.DUPLICATE_OBSERVATION, index, bar))
            seen.add(key)
            if previous_key is not None and key < previous_key:
                findings.append(self._fatal(QualityCode.OUT_OF_ORDER_OBSERVATION, index, bar))
            previous_key = key
            if bar.instrument_id != expected_instrument:
                findings.append(self._fatal(QualityCode.INCONSISTENT_INSTRUMENT, index, bar))
            if bar.timeframe is not expected_timeframe:
                findings.append(self._fatal(QualityCode.INCONSISTENT_TIMEFRAME, index, bar))
            if not self._calendar.contains_interval(bar.start_at, bar.end_at):
                findings.append(self._fatal(QualityCode.UNEXPECTED_SESSION_OBSERVATION, index, bar))
            else:
                session = self._calendar.session_for_date(
                    bar.start_at.astimezone(ZoneInfo(self._calendar.market_timezone)).date()
                )
                if session is None or bar.session_id != session.session_id:
                    findings.append(
                        self._fatal(QualityCode.UNEXPECTED_SESSION_OBSERVATION, index, bar)
                    )
            if stale_after is not None and bar.available_at - bar.end_at > stale_after:
                findings.append(
                    QualityFinding(
                        code=QualityCode.STALE_OBSERVATION,
                        severity=QualitySeverity.WARNING,
                        message="record availability delay exceeds configured threshold",
                        record_index=index,
                        start_at=bar.start_at,
                        end_at=bar.end_at,
                    )
                )

        if bars and coverage_start_at is not None and coverage_end_at is not None:
            assert expected_timeframe is not None
            actual = {(bar.start_at, bar.end_at) for bar in bars}
            for start_at, end_at in self._calendar.expected_intervals(
                coverage_start_at, coverage_end_at, expected_timeframe
            ):
                if (start_at, end_at) not in actual:
                    findings.append(
                        QualityFinding(
                            code=QualityCode.MISSING_INTERVAL,
                            severity=QualitySeverity.WARNING,
                            message=(
                                "expected trading interval is missing; no candle was synthesized"
                            ),
                            start_at=start_at,
                            end_at=end_at,
                        )
                    )
        return DatasetValidationResult(accepted_bars=tuple(bars), findings=tuple(findings))

    @staticmethod
    def _fatal(code: QualityCode, index: int, bar: HistoricalBar) -> QualityFinding:
        return QualityFinding(
            code=code,
            severity=QualitySeverity.FATAL,
            message=code.value.replace("_", " ").lower(),
            record_index=index,
            start_at=bar.start_at,
            end_at=bar.end_at,
        )
