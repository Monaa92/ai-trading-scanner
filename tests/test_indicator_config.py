from datetime import date
from decimal import Decimal

import pytest
from indicator_helpers import bars_for_session, data_slice
from pydantic import ValidationError

from ai_trading_scanner.indicators import (
    ATRConfig,
    EMAConfig,
    PriceBasis,
    ResetPolicy,
    RSIConfig,
    SmoothingMethod,
    VWAPConfig,
    calculate_ema,
    calculate_indicator_configuration_id,
)
from ai_trading_scanner.indicators.models import IndicatorPoint, IndicatorReason, IndicatorSeries


@pytest.mark.parametrize("invalid_period", [0, -1, 1.5, True, "14"])
def test_periods_are_strict_positive_integers(invalid_period: object) -> None:
    with pytest.raises(ValidationError):
        EMAConfig(period=invalid_period)  # type: ignore[arg-type]


def test_methodology_is_explicit_and_unknown_fields_fail() -> None:
    with pytest.raises(ValidationError, match="smoothing"):
        RSIConfig.model_validate({"period": 14})
    with pytest.raises(ValidationError, match="extra"):
        ATRConfig.model_validate({"period": 14, "smoothing": "WILDER", "seed": "last"})
    with pytest.raises(ValidationError, match="price_basis"):
        VWAPConfig.model_validate({"reset_policy": "SESSION"})


def test_configuration_is_immutable_serializable_and_content_identified() -> None:
    first = RSIConfig(period=14, smoothing=SmoothingMethod.WILDER)
    second = RSIConfig.model_validate_json(first.model_dump_json())

    assert first == second
    assert calculate_indicator_configuration_id(first) == calculate_indicator_configuration_id(
        second
    )
    assert calculate_indicator_configuration_id(first) != calculate_indicator_configuration_id(
        RSIConfig(period=13, smoothing=SmoothingMethod.WILDER)
    )
    with pytest.raises(ValidationError, match="frozen"):
        first.period = 10


def test_decimal_values_are_not_configuration_inputs() -> None:
    with pytest.raises(ValidationError):
        EMAConfig(period=Decimal("2"))  # type: ignore[arg-type]


def test_vwap_configuration_names_formula_and_reset_policy() -> None:
    configuration = VWAPConfig(
        price_basis=PriceBasis.TYPICAL_PRICE,
        reset_policy=ResetPolicy.SESSION,
    )

    assert configuration.implementation_version == "bar-typical-price-vwap-v1"
    assert configuration.model_dump(mode="json")["reset_policy"] == "SESSION"


def test_output_availability_and_lineage_are_validated() -> None:
    bar = bars_for_session(date(2024, 7, 2), ["1"])[0]
    result = calculate_ema(data_slice((bar,)), EMAConfig(period=1))

    assert result.unit.value == "PRICE"
    with pytest.raises(ValidationError, match="unavailable indicator point"):
        IndicatorPoint(
            instrument_id=bar.instrument_id,
            timeframe=bar.timeframe,
            session_id=bar.session_id,
            bar_start_at=bar.start_at,
            bar_end_at=bar.end_at,
            bar_available_at=bar.available_at,
            configuration_id=result.configuration_id,
            value=Decimal("1"),
            ready=False,
            reason=IndicatorReason.INSUFFICIENT_HISTORY,
        )

    mismatched = result.model_dump(mode="python")
    mismatched["configuration_id"] = calculate_indicator_configuration_id(EMAConfig(period=2))
    with pytest.raises(ValidationError, match="configuration identity"):
        IndicatorSeries.model_validate(mismatched)

    wrong_unit = result.model_dump(mode="python")
    wrong_unit["unit"] = "PERCENT"
    with pytest.raises(ValidationError, match="unit does not match"):
        IndicatorSeries.model_validate(wrong_unit)
