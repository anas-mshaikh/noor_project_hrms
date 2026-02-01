from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.responses import error as error_envelope

logger = logging.getLogger("app.errors")


class AppError(Exception):
    """
    Application-level exception with a stable error code for clients.
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def _trace_id(request: Request) -> str | None:
    return getattr(request.state, "trace_id", None)


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                trace_id=_trace_id(request),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                code="validation_error",
                message="Request validation failed",
                details=exc.errors(),
                trace_id=_trace_id(request),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # Keep a stable shape for clients while preserving the original detail.
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(
                code="http_error",
                message=str(exc.detail),
                details={"status_code": exc.status_code},
                trace_id=_trace_id(request),
            ),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error trace_id=%s", _trace_id(request), exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_envelope(
                code="internal_error",
                message="Internal server error",
                trace_id=_trace_id(request),
            ),
        )

