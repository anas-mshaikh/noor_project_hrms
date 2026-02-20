"""
Reusable assertion helpers for tests.

Guidelines:
- Keep helpers tiny and predictable.
- Prefer explicit asserts in tests for domain behavior.
- Use helpers mainly for repeated structural checks (envelopes, error codes).
"""

from __future__ import annotations

from typing import Any


def assert_error_code(body: dict[str, Any], *, code: str) -> None:
    """Assert an enveloped error response contains a specific error code."""

    assert body.get("ok") is False, f"expected ok=false, got: {body}"
    err = body.get("error") or {}
    assert err.get("code") == code, f"expected code={code!r}, got: {err}"


def assert_ok(body: dict[str, Any]) -> Any:
    """Assert an enveloped success response and return its data."""

    assert body.get("ok") is True, f"expected ok=true, got: {body}"
    return body.get("data")
