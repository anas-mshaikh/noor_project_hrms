"""
Payroll utilities (Milestone 9).

This module centralizes small helpers used across payroll services:
- Decimal quantization with explicit rounding (money-safe).
- Canonical JSON serialization for deterministic computed_json payloads.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


MONEY_QUANT = Decimal("0.01")


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp (used for computed_at fields)."""

    return datetime.now(timezone.utc)


def money(value: Decimal) -> Decimal:
    """
    Quantize a Decimal money amount to 2dp using ROUND_HALF_UP.

    Why explicit rounding:
    - Payroll must be deterministic across Python versions and environments.
    - Float math is not acceptable for money.
    """

    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def to_decimal(value: Any, *, default: Decimal | None = None) -> Decimal | None:
    """
    Coerce a DB value (NUMERIC/str/int/None) into Decimal.
    """

    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return default


def json_canonical(value: Any) -> str:
    """
    Serialize a JSON-ish value deterministically.

    This is used for computed_json/totals_json so repeated generation produces
    byte-identical JSON where possible.
    """

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

