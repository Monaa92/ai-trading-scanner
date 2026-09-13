"""TOML loading with explicit and redacted validation errors."""

import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ai_trading_scanner.config.models import FoundationConfig


class FoundationConfigError(ValueError):
    """Raised when startup configuration cannot be loaded safely."""


def default_config_text() -> str:
    """Read the version-controlled, bundled safe default configuration."""
    resource = resources.files("ai_trading_scanner").joinpath("defaults/phase1.toml")
    return resource.read_text(encoding="utf-8")


def _validation_summary(error: ValidationError) -> str:
    messages: list[str] = []
    for item in error.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in item["loc"]) or "configuration"
        messages.append(f"{location}: {item['msg']}")
    return "; ".join(messages)


def _read_toml(path: Path | None) -> dict[str, Any]:
    label = "bundled default" if path is None else str(path)
    try:
        content = default_config_text() if path is None else path.read_text(encoding="utf-8")
        parsed = tomllib.loads(content)
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise FoundationConfigError(f"cannot load {label}: {exc}") from exc
    return parsed


def load_foundation_config(path: Path | None = None) -> FoundationConfig:
    """Load and validate startup configuration without implicit fallback."""
    raw = _read_toml(path)
    try:
        return FoundationConfig.model_validate(raw)
    except ValidationError as exc:
        label = "bundled default" if path is None else str(path)
        raise FoundationConfigError(f"invalid {label}: {_validation_summary(exc)}") from exc
