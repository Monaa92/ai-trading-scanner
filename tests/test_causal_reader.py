from datetime import UTC, datetime

import pytest

from ai_trading_scanner.market_data import (
    AdjustmentMethod,
    AvailabilityMode,
    CanonicalDataset,
    CausalBarReader,
    DataProvenance,
    QualityStatus,
    Timeframe,
    synthetic_regular_session_bars,
)


def provenance() -> DataProvenance:
    return DataProvenance(
        provider="synthetic-test",
        timeframe=Timeframe.MINUTE_1,
        source_timezone="America/New_York",
        ingested_at=datetime(2024, 7, 6, tzinfo=UTC),
        adjustment_method=AdjustmentMethod.RAW,
        availability_mode=AvailabilityMode.MODELED,
        modeled_publication_delay_seconds=5,
        calendar_version="exchange-calendars-4.13.2",
        normalization_version="normalizer-v1",
        quality_status=QualityStatus.PASS,
    )


def test_reader_hides_records_until_their_available_at_boundary() -> None:
    dataset = CanonicalDataset.create(provenance(), synthetic_regular_session_bars())
    reader = CausalBarReader(dataset)

    before = reader.slice_as_of(datetime(2024, 7, 2, 13, 31, 4, tzinfo=UTC))
    first_available = reader.slice_as_of(datetime(2024, 7, 2, 13, 31, 5, tzinfo=UTC))
    all_available = reader.slice_as_of(datetime(2024, 7, 2, 13, 32, 5, tzinfo=UTC))

    assert before.bars == ()
    assert len(first_available.bars) == 1
    assert len(all_available.bars) == 2


def test_equivalent_consumers_receive_identical_immutable_slices() -> None:
    dataset = CanonicalDataset.create(provenance(), synthetic_regular_session_bars())
    reader = CausalBarReader(dataset)
    as_of = datetime(2024, 7, 2, 13, 32, 5, tzinfo=UTC)

    slices = [reader.slice_as_of(as_of) for _agent in range(4)]

    assert len({slice_.content_hash_sha256 for slice_ in slices}) == 1
    assert len({slice_.dataset_id for slice_ in slices}) == 1
    assert all(slice_.bars == slices[0].bars for slice_ in slices)


def test_reader_rejects_naive_as_of_time() -> None:
    dataset = CanonicalDataset.create(provenance(), synthetic_regular_session_bars())

    with pytest.raises(ValueError, match="timezone-aware"):
        CausalBarReader(dataset).slice_as_of(datetime(2024, 7, 2, 13, 32))
