from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import AppError

from app.core.responses import ok
from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    return ok({"status": "ok"})


@router.get("/healthz")
def healthz() -> dict[str, object]:
    return ok({"status": "ok"})


@router.get("/readyz")
def readyz() -> dict[str, object]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            revision = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
    except SQLAlchemyError as exc:
        raise AppError(
            code="service.unready",
            message="Service is not ready",
            status_code=503,
            details={"check": "database"},
        ) from exc

    if revision is None:
        raise AppError(
            code="service.unready",
            message="Service is not ready",
            status_code=503,
            details={"check": "alembic_version"},
        )

    return ok({"status": "ready", "revision": revision})
