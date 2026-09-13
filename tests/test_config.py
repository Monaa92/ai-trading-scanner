from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_trading_scanner.config import (
    FoundationConfig,
    FoundationConfigError,
    default_config_text,
    load_foundation_config,
)
from ai_trading_scanner.domain import ApprovalPolicy, ExecutionEnvironment


def valid_config() -> dict[str, object]:
    return {
        "schema_version": "phase1-v1",
        "configuration_version_id": "test-config-v1",
        "execution": {
            "data_run_mode": "HISTORICAL_REPLAY",
            "execution_environment": "SIMULATION",
            "submission_mode": "SIGNAL_ONLY",
            "approval_policy": "MANUAL_APPROVAL",
            "operating_context": "NORMAL",
        },
        "safety": {
            "live_trading_enabled": False,
            "paper_order_submission_enabled": False,
            "broker_connections_enabled": False,
            "external_service_calls_enabled": False,
            "ai_inference_enabled": False,
        },
    }


def test_safe_default_loads_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("OPENAI_API_KEY", "IBKR_PASSWORD", "KRAKEN_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    settings = load_foundation_config()

    assert settings.execution.execution_environment is ExecutionEnvironment.SIMULATION
    assert settings.safety.live_trading_enabled is False
    assert settings.safety.broker_connections_enabled is False
    assert settings.safety.ai_inference_enabled is False


def test_paper_plus_full_auto_is_representable_but_still_signal_only() -> None:
    raw = valid_config()
    execution = raw["execution"]
    assert isinstance(execution, dict)
    execution["execution_environment"] = "PAPER"
    execution["approval_policy"] = "FULL_AUTO"

    settings = FoundationConfig.model_validate(raw)

    assert settings.execution.execution_environment is ExecutionEnvironment.PAPER
    assert settings.execution.approval_policy is ApprovalPolicy.FULL_AUTO
    assert settings.safety.paper_order_submission_enabled is False


def test_operational_live_activation_is_rejected_without_fallback() -> None:
    raw = valid_config()
    execution = raw["execution"]
    assert isinstance(execution, dict)
    execution["execution_environment"] = "LIVE"

    with pytest.raises(ValidationError, match="LIVE operational activation is disabled"):
        FoundationConfig.model_validate(raw)

    assert execution["execution_environment"] == "LIVE"


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("safety", "live_trading_enabled"),
        ("safety", "paper_order_submission_enabled"),
        ("safety", "broker_connections_enabled"),
        ("safety", "external_service_calls_enabled"),
        ("safety", "ai_inference_enabled"),
    ],
)
def test_disabled_capabilities_cannot_be_enabled(section: str, field: str) -> None:
    raw = valid_config()
    target = raw[section]
    assert isinstance(target, dict)
    target[field] = True

    with pytest.raises(ValidationError):
        FoundationConfig.model_validate(raw)


def test_order_enabled_is_rejected_in_phase1() -> None:
    raw = valid_config()
    execution = raw["execution"]
    assert isinstance(execution, dict)
    execution["submission_mode"] = "ORDER_ENABLED"

    with pytest.raises(ValidationError, match="SIGNAL_ONLY only"):
        FoundationConfig.model_validate(raw)


@pytest.mark.parametrize(
    "field", ["risk_limits", "capital_allocation", "api_budget", "credentials"]
)
def test_unimplemented_authority_fields_are_rejected(field: str) -> None:
    raw = valid_config()
    raw[field] = {"enabled": True}

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        FoundationConfig.model_validate(raw)


def test_missing_required_configuration_is_rejected() -> None:
    raw = valid_config()
    del raw["safety"]

    with pytest.raises(ValidationError, match="Field required"):
        FoundationConfig.model_validate(raw)


def test_unknown_environment_and_policy_are_rejected() -> None:
    for field, value in (("execution_environment", "UNKNOWN"), ("approval_policy", "UNKNOWN")):
        raw = deepcopy(valid_config())
        execution = raw["execution"]
        assert isinstance(execution, dict)
        execution[field] = value
        with pytest.raises(ValidationError):
            FoundationConfig.model_validate(raw)


def test_invalid_file_reports_error_and_does_not_load_default(tmp_path: Path) -> None:
    path = tmp_path / "invalid.toml"
    path.write_text('schema_version = "phase1-v1"\n', encoding="utf-8")

    with pytest.raises(FoundationConfigError, match="configuration_version_id: Field required"):
        load_foundation_config(path)


def test_missing_file_reports_explicit_error(tmp_path: Path) -> None:
    path = tmp_path / "missing.toml"

    with pytest.raises(FoundationConfigError, match="cannot load"):
        load_foundation_config(path)


def test_validation_errors_do_not_echo_unknown_sensitive_values(tmp_path: Path) -> None:
    marker = "credential-value-must-not-be-printed"
    path = tmp_path / "sensitive.toml"
    path.write_text(
        f'credentials = "{marker}"\n' + default_config_text(),
        encoding="utf-8",
    )

    with pytest.raises(FoundationConfigError) as captured:
        load_foundation_config(path)

    assert marker not in str(captured.value)
