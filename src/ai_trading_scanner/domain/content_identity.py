"""Canonical serialization used by deterministic content identities."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel


def canonicalize(value: Any) -> Any:
    """Convert supported domain values to stable JSON-compatible content."""
    if isinstance(value, BaseModel):
        return canonicalize(value.model_dump(mode="python", exclude_none=False))
    if isinstance(value, dict):
        return {str(key): canonicalize(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple | list):
        return [canonicalize(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    return value


def canonical_decimal_v2(value: Decimal) -> str:
    """Return the Phase 6 V2 representation of one finite mathematical value."""
    if not value.is_finite():
        raise ValueError("canonical Decimal values must be finite")
    if value.is_zero():
        return "0"
    sign, raw_digits, raw_exponent = value.as_tuple()
    exponent = int(raw_exponent)
    digits = list(raw_digits)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    coefficient = "".join(str(digit) for digit in digits)
    adjusted_exponent = exponent + len(digits) - 1
    mantissa = coefficient[0]
    if len(coefficient) > 1:
        mantissa += "." + coefficient[1:]
    if adjusted_exponent:
        mantissa += f"E{adjusted_exponent:+d}"
    return ("-" if sign else "") + mantissa


def canonicalize_v2(value: Any) -> Any:
    """Versioned canonical form used by pre-completion Phase 6 artifacts."""
    if isinstance(value, BaseModel):
        return canonicalize_v2(value.model_dump(mode="python", exclude_none=False))
    if isinstance(value, dict):
        return {str(key): canonicalize_v2(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple | list):
        return [canonicalize_v2(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return canonical_decimal_v2(value)
    if isinstance(value, Enum):
        return value.value
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(canonicalize(value), sort_keys=True, separators=(",", ":")).encode()


def sha256_content_id(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


def canonical_json_bytes_v2(value: Any) -> bytes:
    return json.dumps(canonicalize_v2(value), sort_keys=True, separators=(",", ":")).encode()


def sha256_content_id_v2(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes_v2(value)).hexdigest()}"
