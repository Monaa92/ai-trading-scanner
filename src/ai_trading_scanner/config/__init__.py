"""Typed, fail-closed foundation configuration."""

from ai_trading_scanner.config.loader import (
    FoundationConfigError,
    default_config_text,
    load_foundation_config,
)
from ai_trading_scanner.config.models import FoundationConfig, Phase1Safety

__all__ = [
    "FoundationConfig",
    "FoundationConfigError",
    "Phase1Safety",
    "default_config_text",
    "load_foundation_config",
]
