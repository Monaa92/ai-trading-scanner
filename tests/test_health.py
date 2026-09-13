import io
import json
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_trading_scanner.api import create_app
from ai_trading_scanner.cli import main
from ai_trading_scanner.config import load_foundation_config


def test_health_cli_succeeds_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    secret_marker = "must-not-appear-in-health-output"
    monkeypatch.setenv("OPENAI_API_KEY", secret_marker)

    def network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("health check attempted a network connection")

    monkeypatch.setattr(socket, "create_connection", network_forbidden)
    output = io.StringIO()
    errors = io.StringIO()

    exit_code = main(["health"], stdout=output, stderr=errors)
    report = json.loads(output.getvalue())

    assert exit_code == 0
    assert errors.getvalue() == ""
    assert report["status"] == "healthy"
    assert report["execution_environment"] == "SIMULATION"
    assert report["submission_mode"] == "SIGNAL_ONLY"
    assert report["live_enabled"] is False
    assert report["broker_connections_enabled"] is False
    assert report["external_services_required"] is False
    assert secret_marker not in output.getvalue()


def test_health_cli_fails_nonzero_for_invalid_configuration(tmp_path: Path) -> None:
    path = tmp_path / "live.toml"
    path.write_text(
        """
schema_version = "phase1-v1"
configuration_version_id = "invalid-live-v1"

[execution]
data_run_mode = "HISTORICAL_REPLAY"
execution_environment = "LIVE"
submission_mode = "SIGNAL_ONLY"
approval_policy = "MANUAL_APPROVAL"
operating_context = "NORMAL"

[safety]
live_trading_enabled = false
paper_order_submission_enabled = false
broker_connections_enabled = false
external_service_calls_enabled = false
ai_inference_enabled = false
""".strip(),
        encoding="utf-8",
    )
    output = io.StringIO()
    errors = io.StringIO()

    exit_code = main(["health", "--config", str(path)], stdout=output, stderr=errors)

    assert exit_code == 2
    assert output.getvalue() == ""
    assert "LIVE operational activation is disabled" in errors.getvalue()
    assert "SIMULATION" not in errors.getvalue()


def test_fastapi_health_boundary_uses_validated_configuration() -> None:
    client = TestClient(create_app(load_foundation_config()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["live_enabled"] is False
