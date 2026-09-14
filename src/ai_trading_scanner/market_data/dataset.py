"""Content identity and causal access for canonical datasets."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, field_validator

from ai_trading_scanner.domain import DatasetId, InstrumentId
from ai_trading_scanner.domain.content_identity import canonical_json_bytes, sha256_content_id
from ai_trading_scanner.market_data.models import DataProvenance, HistoricalBar, QualityStatus
from ai_trading_scanner.market_data.quality import DatasetValidator, QualityCode, QualityFinding


def calculate_dataset_id(provenance: DataProvenance, bars: Iterable[HistoricalBar]) -> DatasetId:
    ordered_bars = sorted(
        bars,
        key=lambda bar: (str(bar.instrument_id), bar.start_at, bar.timeframe.value),
    )
    payload = {"provenance": provenance, "bars": ordered_bars}
    return DatasetId.parse(sha256_content_id(payload))


class CanonicalDataset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: DatasetId
    provenance: DataProvenance
    bars: tuple[HistoricalBar, ...]
    quality_findings: tuple[QualityFinding, ...]

    @classmethod
    def create(cls, provenance: DataProvenance, bars: Iterable[HistoricalBar]) -> CanonicalDataset:
        supplied_bars = tuple(bars)
        if not supplied_bars:
            raise ValueError("canonical dataset requires at least one bar")
        validation = DatasetValidator().validate(
            supplied_bars,
            coverage_start_at=provenance.covered_start_at,
            coverage_end_at=provenance.covered_end_at,
        )
        if not validation.usable:
            codes = sorted({finding.code.value for finding in validation.findings})
            raise ValueError(f"canonical dataset contains fatal quality findings: {codes}")
        missing_findings = {
            (finding.start_at, finding.end_at)
            for finding in validation.findings
            if finding.code is QualityCode.MISSING_INTERVAL
        }
        declared_missing = {
            (interval.start_at, interval.end_at) for interval in provenance.missing_intervals
        }
        if validation.findings:
            if provenance.quality_status is not QualityStatus.WARN:
                raise ValueError("dataset warnings require WARN provenance quality status")
            if missing_findings != declared_missing:
                raise ValueError("detected missing intervals must match provenance")
        elif provenance.quality_status is not QualityStatus.PASS:
            raise ValueError("validated dataset without findings requires PASS quality status")
        for bar in supplied_bars:
            if bar.timeframe is not provenance.timeframe:
                raise ValueError("bar timeframe does not match dataset provenance")
            if bar.availability_mode is not provenance.availability_mode:
                raise ValueError("bar availability mode does not match dataset provenance")
            delay = provenance.modeled_publication_delay_seconds
            if delay is not None and bar.available_at < bar.end_at + timedelta(seconds=delay):
                raise ValueError("bar is available before the modeled publication delay")
        frozen_bars = tuple(
            sorted(
                supplied_bars,
                key=lambda bar: (str(bar.instrument_id), bar.start_at, bar.timeframe.value),
            )
        )
        return cls(
            dataset_id=calculate_dataset_id(provenance, frozen_bars),
            provenance=provenance,
            bars=frozen_bars,
            quality_findings=validation.findings,
        )


class MarketDataSlice(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: DatasetId
    as_of: datetime
    bars: tuple[HistoricalBar, ...]
    content_hash_sha256: str
    quality_findings: tuple[QualityFinding, ...]

    @field_validator("as_of")
    @classmethod
    def require_aware_as_of(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return value.astimezone(UTC)


class CausalBarReader:
    """Expose immutable bars only after each bar's recorded availability time."""

    def __init__(self, dataset: CanonicalDataset) -> None:
        self._dataset_id = dataset.dataset_id
        self._bars = dataset.bars
        self._quality_findings = dataset.quality_findings
        delay = dataset.provenance.modeled_publication_delay_seconds
        self._finding_delay = timedelta(seconds=delay) if delay is not None else timedelta(0)

    def slice_as_of(
        self, as_of: datetime, instrument_ids: frozenset[InstrumentId] | None = None
    ) -> MarketDataSlice:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        as_of = as_of.astimezone(UTC)
        bars = tuple(
            bar
            for bar in self._bars
            if bar.available_at <= as_of
            and (instrument_ids is None or bar.instrument_id in instrument_ids)
        )
        encoded = canonical_json_bytes(bars)
        visible_findings = tuple(
            finding
            for finding in self._quality_findings
            if finding.end_at is None or finding.end_at + self._finding_delay <= as_of
        )
        return MarketDataSlice(
            dataset_id=self._dataset_id,
            as_of=as_of,
            bars=bars,
            content_hash_sha256=hashlib.sha256(encoded).hexdigest(),
            quality_findings=visible_findings,
        )
