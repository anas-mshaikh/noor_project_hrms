"""
HR/admin endpoints for profile change requests (Milestone 6).

Routes:
- GET /api/v1/hr/profile-change-requests

Approvals are handled via the generic workflow inbox endpoints; this router is
for reporting/listing only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.profile_change.policies import require_profile_change_read
from app.domains.profile_change.schemas import (
    ProfileChangeRequestListOut,
    ProfileChangeRequestOut,
)
from app.domains.profile_change.service import ProfileChangeService
from app.shared.types import AuthContext


router = APIRouter(prefix="/hr", tags=["profile-change"])
_svc = ProfileChangeService()


def _parse_cursor(cursor: str) -> tuple[datetime, UUID]:
    """Parse a cursor of the form "ts|uuid"."""

    try:
        ts_raw, id_raw = cursor.split("|", 1)
        ts = datetime.fromisoformat(ts_raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts, UUID(id_raw)
    except Exception as e:  # noqa: BLE001
        raise AppError(
            code="validation_error",
            message=f"invalid cursor: {cursor!r}",
            status_code=400,
        ) from e


@router.get("/profile-change-requests")
def list_profile_change_requests(
    status: str | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    ctx: AuthContext = Depends(require_profile_change_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cur = _parse_cursor(cursor) if cursor else None
    rows, next_cursor = _svc.list_requests_hr(
        db,
        ctx=ctx,
        status=status,
        branch_id=branch_id,
        limit=limit,
        cursor=cur,
    )
    items = [ProfileChangeRequestOut(**r) for r in rows]
    return ok(
        ProfileChangeRequestListOut(items=items, next_cursor=next_cursor).model_dump()
    )
