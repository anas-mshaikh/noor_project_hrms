from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.http")


class TraceIdMiddleware:
    """
    Adds a request-scoped correlation_id and emits a single structured log line per request.

    - correlation_id is stored on request.state.correlation_id
    - response header: X-Correlation-Id

    Backwards compatibility:
    - If the client sends X-Trace-Id, we treat it as the correlation id.
    - We also store the value on request.state.trace_id for legacy code paths.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Starlette stores request.state on scope["state"] (a dict-like).
        state = scope.setdefault("state", {})
        req_headers = dict(scope.get("headers") or [])
        correlation_id = (
            req_headers.get(b"x-correlation-id")
            or req_headers.get(b"x-trace-id")
            or uuid4().hex.encode()
        ).decode()
        state["correlation_id"] = correlation_id
        state["trace_id"] = correlation_id  # legacy alias

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers") or [])
                headers.append((b"x-correlation-id", correlation_id.encode()))
                # Legacy header for older clients/tools.
                headers.append((b"x-trace-id", correlation_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0

            user_id = state.get("user_id")
            scope_obj = state.get("scope")
            tenant_id = getattr(scope_obj, "tenant_id", None) if scope_obj is not None else None
            company_id = getattr(scope_obj, "company_id", None) if scope_obj is not None else None
            branch_id = getattr(scope_obj, "branch_id", None) if scope_obj is not None else None

            logger.info(
                "request method=%s path=%s status=%s duration_ms=%.2f correlation_id=%s user_id=%s tenant_id=%s company_id=%s branch_id=%s",
                scope.get("method"),
                scope.get("path"),
                status_code,
                duration_ms,
                correlation_id,
                user_id,
                tenant_id,
                company_id,
                branch_id,
            )
