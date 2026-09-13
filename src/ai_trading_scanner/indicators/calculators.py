"""Deterministic, session-reset indicator calculations over canonical bars."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from zoneinfo import ZoneInfo

from ai_trading_scanner.domain import InstrumentId
from ai_trading_scanner.indicators.models import (
    ATRConfig,
    EMAConfig,
    IndicatorConfiguration,
    IndicatorPoint,
    IndicatorReason,
    IndicatorSeries,
    IndicatorUnit,
    RSIConfig,
    VWAPConfig,
    calculate_indicator_configuration_id,
)
from ai_trading_scanner.market_data import (
    DatasetValidator,
    HistoricalBar,
    MarketDataSlice,
    QualitySeverity,
    Timeframe,
    UsEquitiesCalendar,
)

_ARITHMETIC = Context(prec=34, rounding=ROUND_HALF_EVEN)


class IncrementalIndicator[ConfigT: IndicatorConfiguration](ABC):
    """Explicit isolated state for sequential indicator calculation."""

    def __init__(self, configuration: ConfigT) -> None:
        self.configuration = configuration
        self.configuration_id = calculate_indicator_configuration_id(configuration)
        self._calendar = UsEquitiesCalendar()
        self._instrument_id: InstrumentId | None = None
        self._timeframe: Timeframe | None = None
        self._session_id: str | None = None
        self._previous_bar: HistoricalBar | None = None
        self._gap_restart = False

    def update(self, bar: HistoricalBar) -> IndicatorPoint:
        self._validate_bar(bar)
        new_session = self._session_id != bar.session_id
        gap = (
            not new_session
            and self._previous_bar is not None
            and bar.start_at != self._previous_bar.end_at
        )
        if new_session or gap:
            self._reset()
            self._gap_restart = gap
        value, reason = self._update_value(bar, new_session=new_session, gap=gap)
        self._session_id = bar.session_id
        self._previous_bar = bar
        return IndicatorPoint(
            instrument_id=bar.instrument_id,
            timeframe=bar.timeframe,
            session_id=bar.session_id,
            bar_start_at=bar.start_at,
            bar_end_at=bar.end_at,
            bar_available_at=bar.available_at,
            configuration_id=self.configuration_id,
            value=value,
            ready=value is not None,
            reason=IndicatorReason.READY if value is not None else reason,
        )

    def _validate_bar(self, bar: HistoricalBar) -> None:
        if not self._calendar.contains_interval(bar.start_at, bar.end_at):
            raise ValueError("indicator input bar is outside an XNYS regular session")
        local_date = bar.start_at.astimezone(ZoneInfo(self._calendar.market_timezone)).date()
        session = self._calendar.session_for_date(local_date)
        if session is None or session.session_id != bar.session_id:
            raise ValueError("indicator input bar has an invalid session identity")
        if self._instrument_id is None:
            self._instrument_id = bar.instrument_id
            self._timeframe = bar.timeframe
        elif bar.instrument_id != self._instrument_id or bar.timeframe is not self._timeframe:
            raise ValueError("one incremental calculator accepts one instrument and timeframe")
        if self._previous_bar is not None and bar.start_at <= self._previous_bar.start_at:
            raise ValueError("indicator input bars must be strictly ordered")

    def _warmup_reason(self) -> IndicatorReason:
        if self._gap_restart:
            return IndicatorReason.MISSING_INTERVAL
        return IndicatorReason.INSUFFICIENT_HISTORY

    @abstractmethod
    def _reset(self) -> None: ...

    @abstractmethod
    def _update_value(
        self, bar: HistoricalBar, *, new_session: bool, gap: bool
    ) -> tuple[Decimal | None, IndicatorReason]: ...


class EMACalculator(IncrementalIndicator[EMAConfig]):
    def __init__(self, configuration: EMAConfig) -> None:
        super().__init__(configuration)
        self._closes: list[Decimal] = []
        self._ema: Decimal | None = None

    def _reset(self) -> None:
        self._closes = []
        self._ema = None

    def _update_value(
        self, bar: HistoricalBar, *, new_session: bool, gap: bool
    ) -> tuple[Decimal | None, IndicatorReason]:
        del new_session
        self._closes.append(bar.close)
        with localcontext(_ARITHMETIC):
            if len(self._closes) < self.configuration.period:
                return None, self._warmup_reason()
            if self._ema is None:
                self._ema = sum(self._closes, Decimal(0)) / Decimal(self.configuration.period)
            else:
                alpha = Decimal(2) / Decimal(self.configuration.period + 1)
                self._ema = alpha * bar.close + (Decimal(1) - alpha) * self._ema
        return self._ema, IndicatorReason.READY


class RSICalculator(IncrementalIndicator[RSIConfig]):
    def __init__(self, configuration: RSIConfig) -> None:
        super().__init__(configuration)
        self._previous_close: Decimal | None = None
        self._gains: list[Decimal] = []
        self._losses: list[Decimal] = []
        self._average_gain: Decimal | None = None
        self._average_loss: Decimal | None = None

    def _reset(self) -> None:
        self._previous_close = None
        self._gains = []
        self._losses = []
        self._average_gain = None
        self._average_loss = None

    def _update_value(
        self, bar: HistoricalBar, *, new_session: bool, gap: bool
    ) -> tuple[Decimal | None, IndicatorReason]:
        del new_session
        if self._previous_close is None:
            self._previous_close = bar.close
            return None, self._warmup_reason()
        with localcontext(_ARITHMETIC):
            change = bar.close - self._previous_close
            self._previous_close = bar.close
            gain = max(change, Decimal(0))
            loss = max(-change, Decimal(0))
            if self._average_gain is None or self._average_loss is None:
                self._gains.append(gain)
                self._losses.append(loss)
                if len(self._gains) < self.configuration.period:
                    return None, self._warmup_reason()
                period = Decimal(self.configuration.period)
                self._average_gain = sum(self._gains, Decimal(0)) / period
                self._average_loss = sum(self._losses, Decimal(0)) / period
            else:
                period = Decimal(self.configuration.period)
                self._average_gain = (
                    Decimal(self.configuration.period - 1) * self._average_gain + gain
                ) / period
                self._average_loss = (
                    Decimal(self.configuration.period - 1) * self._average_loss + loss
                ) / period
            return self._rsi(), IndicatorReason.READY

    def _rsi(self) -> Decimal:
        assert self._average_gain is not None and self._average_loss is not None
        if self._average_loss == 0:
            return Decimal(50) if self._average_gain == 0 else Decimal(100)
        if self._average_gain == 0:
            return Decimal(0)
        ratio = self._average_gain / self._average_loss
        return Decimal(100) - Decimal(100) / (Decimal(1) + ratio)


class ATRCalculator(IncrementalIndicator[ATRConfig]):
    def __init__(self, configuration: ATRConfig) -> None:
        super().__init__(configuration)
        self._previous_close: Decimal | None = None
        self._true_ranges: list[Decimal] = []
        self._atr: Decimal | None = None

    def _reset(self) -> None:
        self._previous_close = None
        self._true_ranges = []
        self._atr = None

    def _update_value(
        self, bar: HistoricalBar, *, new_session: bool, gap: bool
    ) -> tuple[Decimal | None, IndicatorReason]:
        del new_session
        with localcontext(_ARITHMETIC):
            true_range = bar.high - bar.low
            if self._previous_close is not None:
                true_range = max(
                    true_range,
                    abs(bar.high - self._previous_close),
                    abs(bar.low - self._previous_close),
                )
            self._previous_close = bar.close
            self._true_ranges.append(true_range)
            if len(self._true_ranges) < self.configuration.period:
                return None, self._warmup_reason()
            if self._atr is None:
                self._atr = sum(self._true_ranges, Decimal(0)) / Decimal(self.configuration.period)
            else:
                self._atr = (
                    Decimal(self.configuration.period - 1) * self._atr + true_range
                ) / Decimal(self.configuration.period)
        return self._atr, IndicatorReason.READY


class VWAPCalculator(IncrementalIndicator[VWAPConfig]):
    def __init__(self, configuration: VWAPConfig) -> None:
        super().__init__(configuration)
        self._cumulative_price_volume = Decimal(0)
        self._cumulative_volume = Decimal(0)
        self._complete_session_prefix = True

    def _reset(self) -> None:
        self._cumulative_price_volume = Decimal(0)
        self._cumulative_volume = Decimal(0)
        self._complete_session_prefix = True

    def _update_value(
        self, bar: HistoricalBar, *, new_session: bool, gap: bool
    ) -> tuple[Decimal | None, IndicatorReason]:
        if new_session:
            local_date = bar.start_at.astimezone(ZoneInfo(self._calendar.market_timezone)).date()
            session = self._calendar.session_for_date(local_date)
            assert session is not None
            self._complete_session_prefix = bar.start_at == session.open_at
        if gap:
            self._complete_session_prefix = False
        if not self._complete_session_prefix:
            return None, (
                IndicatorReason.MISSING_INTERVAL
                if gap
                else IndicatorReason.INCOMPLETE_SESSION_PREFIX
            )
        with localcontext(_ARITHMETIC):
            typical_price = (bar.high + bar.low + bar.close) / Decimal(3)
            self._cumulative_price_volume += typical_price * bar.volume
            self._cumulative_volume += bar.volume
            if self._cumulative_volume == 0:
                return None, IndicatorReason.ZERO_CUMULATIVE_VOLUME
            return (
                self._cumulative_price_volume / self._cumulative_volume,
                IndicatorReason.READY,
            )


def _validate_slice(data: MarketDataSlice) -> None:
    if not data.bars:
        raise ValueError("indicator calculation requires at least one causal bar")
    if any(bar.available_at > data.as_of for bar in data.bars):
        raise ValueError("indicator input contains a bar unavailable at the slice as_of time")
    if len({bar.currency for bar in data.bars}) != 1:
        raise ValueError("indicator input bars must use one currency/price unit")
    validation = DatasetValidator().validate(data.bars)
    if not validation.usable:
        codes = sorted(
            finding.code.value
            for finding in validation.findings
            if finding.severity is QualitySeverity.FATAL
        )
        raise ValueError(f"indicator input contains fatal quality findings: {codes}")
    if any(finding.severity is QualitySeverity.FATAL for finding in data.quality_findings):
        raise ValueError("indicator input carries fatal quality findings")


def _calculate[ConfigT: IndicatorConfiguration](
    data: MarketDataSlice,
    calculator: IncrementalIndicator[ConfigT],
) -> IndicatorSeries:
    _validate_slice(data)
    points = tuple(calculator.update(bar) for bar in data.bars)
    return IndicatorSeries(
        dataset_id=data.dataset_id,
        input_slice_hash_sha256=data.content_hash_sha256,
        as_of=data.as_of,
        latest_available_at=max(bar.available_at for bar in data.bars),
        configuration=calculator.configuration,
        configuration_id=calculator.configuration_id,
        unit=(
            IndicatorUnit.PERCENT
            if isinstance(calculator.configuration, RSIConfig)
            else IndicatorUnit.PRICE
        ),
        points=points,
        quality_findings=data.quality_findings,
    )


def calculate_ema(data: MarketDataSlice, configuration: EMAConfig) -> IndicatorSeries:
    return _calculate(data, EMACalculator(configuration))


def calculate_rsi(data: MarketDataSlice, configuration: RSIConfig) -> IndicatorSeries:
    return _calculate(data, RSICalculator(configuration))


def calculate_atr(data: MarketDataSlice, configuration: ATRConfig) -> IndicatorSeries:
    return _calculate(data, ATRCalculator(configuration))


def calculate_vwap(data: MarketDataSlice, configuration: VWAPConfig) -> IndicatorSeries:
    return _calculate(data, VWAPCalculator(configuration))


def incremental_points[ConfigT: IndicatorConfiguration](
    calculator: IncrementalIndicator[ConfigT], bars: Iterable[HistoricalBar]
) -> tuple[IndicatorPoint, ...]:
    """Calculate explicitly from caller-owned state for replay equivalence tests."""
    return tuple(calculator.update(bar) for bar in bars)
