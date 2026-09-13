from datetime import UTC, datetime
from decimal import Decimal

from ai_trading_scanner.market_data import (
    AdjustmentMethod,
    AvailabilityMode,
    CanonicalDataset,
    DataProvenance,
    HistoricalBar,
    MissingInterval,
    QualityStatus,
    Timeframe,
    calculate_dataset_id,
    synthetic_regular_session_bars,
)


def provenance(**changes: object) -> DataProvenance:
    values: dict[str, object] = {
        "provider": "synthetic-test",
        "source_dataset_id": "fixture-2024-07-02",
        "source_dataset_version": "v1",
        "universe_reference": "us-equity-fixture-v1",
        "timeframe": Timeframe.MINUTE_1,
        "source_timezone": "America/New_York",
        "requested_start_at": datetime(2024, 7, 2, 13, 30, tzinfo=UTC),
        "requested_end_at": datetime(2024, 7, 2, 13, 32, tzinfo=UTC),
        "covered_start_at": datetime(2024, 7, 2, 13, 30, tzinfo=UTC),
        "covered_end_at": datetime(2024, 7, 2, 13, 32, tzinfo=UTC),
        "ingested_at": datetime(2024, 7, 6, tzinfo=UTC),
        "adjustment_method": AdjustmentMethod.RAW,
        "availability_mode": AvailabilityMode.MODELED,
        "modeled_publication_delay_seconds": 5,
        "calendar_version": "exchange-calendars-4.13.2",
        "normalization_version": "normalizer-v1",
        "quality_status": QualityStatus.PASS,
    }
    values.update(changes)
    return DataProvenance.model_validate(values)


def test_dataset_id_is_stable_for_same_content_and_order_independent() -> None:
    bars = synthetic_regular_session_bars()

    first = calculate_dataset_id(provenance(), bars)
    second = calculate_dataset_id(provenance(), reversed(bars))

    assert first == second
    assert str(first).startswith("sha256:")


def test_dataset_id_changes_when_content_or_provenance_changes() -> None:
    bars = synthetic_regular_session_bars()
    changed_raw = bars[0].model_dump(mode="python")
    changed_raw["close"] = Decimal("100.11")
    changed: HistoricalBar = HistoricalBar.model_validate(changed_raw)

    original_id = calculate_dataset_id(provenance(), bars)
    assert calculate_dataset_id(provenance(), (changed, bars[1])) != original_id
    assert (
        calculate_dataset_id(provenance(adjustment_method=AdjustmentMethod.SPLIT_ADJUSTED), bars)
        != original_id
    )


def test_canonical_dataset_is_immutable_and_self_identifying() -> None:
    dataset = CanonicalDataset.create(provenance(), synthetic_regular_session_bars())

    assert dataset.dataset_id == calculate_dataset_id(dataset.provenance, dataset.bars)
    assert isinstance(dataset.bars, tuple)


def test_canonical_dataset_rejects_sequence_that_failed_quality_validation() -> None:
    first, second = synthetic_regular_session_bars()

    try:
        CanonicalDataset.create(provenance(), (second, first))
    except ValueError as exc:
        assert "OUT_OF_ORDER_OBSERVATION" in str(exc)
    else:
        raise AssertionError("out-of-order observations entered a canonical dataset")


def test_canonical_dataset_enforces_modeled_publication_delay() -> None:
    bars = synthetic_regular_session_bars()
    raw = bars[0].model_dump(mode="python")
    raw["available_at"] = raw["end_at"]
    early = HistoricalBar.model_validate(raw)

    try:
        CanonicalDataset.create(
            provenance(
                requested_start_at=None,
                requested_end_at=None,
                covered_start_at=None,
                covered_end_at=None,
            ),
            (early,),
        )
    except ValueError as exc:
        assert "modeled publication delay" in str(exc)
    else:
        raise AssertionError("early data bypassed the modeled availability boundary")


def test_canonical_dataset_requires_quality_warnings_in_provenance() -> None:
    bars = synthetic_regular_session_bars()
    one_bar = bars[:1]

    try:
        CanonicalDataset.create(provenance(), one_bar)
    except ValueError as exc:
        assert "WARN provenance" in str(exc)
    else:
        raise AssertionError("quality warnings were omitted from provenance")

    documented = provenance(
        quality_status=QualityStatus.WARN,
        missing_intervals=(MissingInterval(start_at=bars[1].start_at, end_at=bars[1].end_at),),
    )
    dataset = CanonicalDataset.create(documented, one_bar)

    assert dataset.provenance.quality_status is QualityStatus.WARN
    assert [finding.code.value for finding in dataset.quality_findings] == ["MISSING_INTERVAL"]
