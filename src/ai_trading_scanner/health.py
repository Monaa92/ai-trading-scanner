"""Offline foundation health reporting."""

import platform
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ai_trading_scanner import __version__
from ai_trading_scanner.config.models import FoundationConfig
from ai_trading_scanner.domain.execution import ApprovalPolicy, ExecutionEnvironment, SubmissionMode
from ai_trading_scanner.indicators import validate_offline_indicator_fixture
from ai_trading_scanner.market_data import UsEquitiesCalendar, validate_offline_fixture


class HealthReport(BaseModel):
    """Non-sensitive readiness information for the local foundation."""

    model_config = ConfigDict(frozen=True)

    status: Literal["healthy"]
    application: Literal["ai-trading-scanner"]
    version: str
    runtime: str
    configuration_version_id: str
    execution_environment: ExecutionEnvironment
    submission_mode: SubmissionMode
    approval_policy: ApprovalPolicy
    live_enabled: Literal[False]
    broker_connections_enabled: Literal[False]
    external_services_required: Literal[False]
    market_data_schema_available: Literal[True]
    xnys_calendar_available: Literal[True]
    synthetic_fixture_validated: Literal[True]
    deterministic_indicators_validated: Literal[True]


def build_health_report(settings: FoundationConfig) -> HealthReport:
    """Build a report from an already validated, immutable configuration."""
    calendar = UsEquitiesCalendar()
    if calendar.session_for_date(date(2024, 7, 2)) is None:
        raise RuntimeError("pinned XNYS calendar did not resolve a known trading session")
    if not validate_offline_fixture():
        raise RuntimeError("synthetic market-data fixture failed validation")
    if not validate_offline_indicator_fixture():
        raise RuntimeError("deterministic indicator fixture failed validation")
    return HealthReport(
        status="healthy",
        application="ai-trading-scanner",
        version=__version__,
        runtime=f"Python {platform.python_version()}",
        configuration_version_id=str(settings.configuration_version_id),
        execution_environment=settings.execution.execution_environment,
        submission_mode=settings.execution.submission_mode,
        approval_policy=settings.execution.approval_policy,
        live_enabled=False,
        broker_connections_enabled=False,
        external_services_required=False,
        market_data_schema_available=True,
        xnys_calendar_available=True,
        synthetic_fixture_validated=True,
        deterministic_indicators_validated=True,
    )
