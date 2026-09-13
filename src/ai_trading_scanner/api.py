"""Minimal local FastAPI boundary for foundation readiness."""

from fastapi import FastAPI

from ai_trading_scanner import __version__
from ai_trading_scanner.config import FoundationConfig, load_foundation_config
from ai_trading_scanner.health import HealthReport, build_health_report


def create_app(settings: FoundationConfig | None = None) -> FastAPI:
    """Create the local API after fail-closed configuration validation."""
    resolved = settings if settings is not None else load_foundation_config()
    api = FastAPI(
        title="AI Trading Scanner",
        version=__version__,
        description="Phase 1 offline foundation; no trading or external integrations.",
    )

    @api.get("/health", response_model=HealthReport)
    def health() -> HealthReport:
        return build_health_report(resolved)

    return api


app = create_app()
