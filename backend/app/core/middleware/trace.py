from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.http")


class TraceIdMiddleware:
    """
    Adds a request-scoped trace_id and emits a single structured log line per request.

    - trace_id is stored on request.state.trace_id
    - response header: X-Trace-Id
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
        trace_id = (req_headers.get(b"x-trace-id") or uuid4().hex.encode()).decode()
        state["trace_id"] = trace_id

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers") or [])
                headers.append((b"x-trace-id", trace_id.encode()))
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
                "request method=%s path=%s status=%s duration_ms=%.2f trace_id=%s user_id=%s tenant_id=%s company_id=%s branch_id=%s",
                scope.get("method"),
                scope.get("path"),
                status_code,
                duration_ms,
                trace_id,
                user_id,
                tenant_id,
                company_id,
                branch_id,
            )
