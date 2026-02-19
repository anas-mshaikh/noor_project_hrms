"""
Profile change v1 utilities (Milestone 6).

This module contains small, shared helpers used by multiple profile-change
services:
- UTC timestamp helper (consistent "now" for DB writes and audit records)
- Canonical JSON serialization helper (stable equality checks / idempotency)

Keeping these utilities here prevents circular imports between:
- change_set normalization/validation
- API-facing service
- workflow terminal hook apply service
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc)


def json_canonical(value: Any) -> str:
    """
    Serialize a Python value into a stable JSON string.

    We use this to:
    - compare JSON payloads for idempotency checks
    - write JSONB parameters in a consistent form

    Notes:
    - Keys are sorted so dict order does not affect equality.
    - Separators are compact to reduce storage size.
    - UUIDs/dates are stringified via `default=str`.
    """

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
