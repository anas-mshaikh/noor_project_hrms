"""
HTTP API test client wrapper (enterprise testing infra).

Why this exists:
- Centralizes the response envelope handling:
    success: {"ok": true, "data": ...}
    error:   {"ok": false, "error": {"code": "...", ...}}
- Makes tests more readable by returning unwrapped `data` on success.
- Makes failures actionable by raising AssertionError with error code/message.

Important:
- This wrapper is intended for JSON endpoints.
- For raw endpoints (e.g., file downloads), callers should use `raw_get(...)`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from fastapi.testclient import TestClient


@dataclass(frozen=True)
class ApiClient:
    """Small wrapper around FastAPI TestClient with stable envelope unwrapping."""

    client: TestClient
    headers: Mapping[str, str]

    # ------------------------------------------------------------------
    # JSON helpers (unwrap envelope)
    # ------------------------------------------------------------------
    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """GET a JSON endpoint and return the unwrapped `data` payload."""

        r = self.client.get(path, headers=dict(self.headers), params=params)
        return self._unwrap_json(r)

    def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        files: Any = None,
    ) -> Any:
        """POST a JSON endpoint and return the unwrapped `data` payload."""

        r = self.client.post(path, headers=dict(self.headers), json=json, files=files)
        return self._unwrap_json(r)

    def patch(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        """PATCH a JSON endpoint and return the unwrapped `data` payload."""

        r = self.client.patch(path, headers=dict(self.headers), json=json)
        return self._unwrap_json(r)

    def put(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        """PUT a JSON endpoint and return the unwrapped `data` payload."""

        r = self.client.put(path, headers=dict(self.headers), json=json)
        return self._unwrap_json(r)

    # ------------------------------------------------------------------
    # Raw helpers (caller inspects response)
    # ------------------------------------------------------------------
    def raw_get(self, path: str, *, params: dict[str, Any] | None = None):
        """GET without envelope handling (for file downloads / streaming)."""

        return self.client.get(path, headers=dict(self.headers), params=params)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _unwrap_json(self, response) -> Any:
        """
        Enforce the stable JSON envelope.

        On success:
          - returns body["data"]

        On error:
          - raises AssertionError with a concise message that includes the
            error code and message.
        """

        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            raise AssertionError(f"expected JSON response, got {content_type}: {response.text}")

        body = response.json()
        assert "ok" in body, response.text
        if body["ok"] is True:
            return body.get("data")

        err = body.get("error") or {}
        code = err.get("code")
        msg = err.get("message")
        raise AssertionError(f"{response.status_code} {code} {msg}: {response.text}")
