from __future__ import annotations

from typing import Any


def ok(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Standard success envelope for new enterprise APIs.

    Note: We do NOT retrofit legacy endpoints yet to avoid breaking clients.
    """

    payload: dict[str, Any] = {"ok": True, "data": data}
    if meta is not None:
        payload["meta"] = meta
    return payload


def error(
    *,
    code: str,
    message: str,
    details: Any | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """
    Standard error envelope for new enterprise APIs.
    """

    err: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    if trace_id is not None:
        err["trace_id"] = trace_id
    return {"ok": False, "error": err}

