"""Offline command-line entry point."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from ai_trading_scanner.config import FoundationConfigError, load_foundation_config
from ai_trading_scanner.health import build_health_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-trading-scanner")
    commands = parser.add_subparsers(dest="command", required=True)
    health = commands.add_parser("health", help="validate the offline foundation")
    health.add_argument(
        "--config",
        type=Path,
        help="optional TOML configuration path; bundled safe default is used when omitted",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Validate configuration and print a deterministic health report."""
    output = stdout if stdout is not None else sys.stdout
    errors = stderr if stderr is not None else sys.stderr
    arguments = _parser().parse_args(argv)

    try:
        settings = load_foundation_config(arguments.config)
    except FoundationConfigError as exc:
        print(f"health check failed: {exc}", file=errors)
        return 2

    report = build_health_report(settings)
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True), file=output)
    return 0
