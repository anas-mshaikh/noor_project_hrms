from __future__ import annotations

import importlib

from fastapi import APIRouter, FastAPI

from app.core.errors import install_exception_handlers
from app.core.middleware.trace import TraceIdMiddleware


def make_app(*router_modules: str, prefix: str = "/api/v1") -> FastAPI:
    """
    Create a small FastAPI app for tests with dynamic router imports.

    Router modules are imported lazily to avoid importing DB/config-dependent
    modules when DATABASE_URL is not set (tests are skipped in that case).
    """

    app = FastAPI()
    app.add_middleware(TraceIdMiddleware)
    install_exception_handlers(app)

    for module_path in router_modules:
        module = importlib.import_module(module_path)
        router = getattr(module, "router", None)
        if not isinstance(router, APIRouter):
            raise RuntimeError(f"{module_path}.router is missing or not an APIRouter")
        app.include_router(router, prefix=prefix)

    return app

