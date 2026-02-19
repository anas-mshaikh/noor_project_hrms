"""
ESS endpoints for HR profile change requests (Milestone 6).

Routes:
- POST /api/v1/ess/me/profile-change-requests
- GET  /api/v1/ess/me/profile-change-requests
- POST /api/v1/ess/me/profile-change-requests/{request_id}/cancel
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.profile_change.policies import (
    require_profile_change_read,
    require_profile_change_submit,
)
from app.domains.profile_change.schemas import (
    ProfileChangeCancelOut,
    ProfileChangeCreateIn,
    ProfileChangeRequestListOut,
    ProfileChangeRequestOut,
)
from app.domains.profile_change.service import ProfileChangeService
from app.shared.types import AuthContext


router = APIRouter(prefix="/ess", tags=["profile-change"])
_svc = ProfileChangeService()


def _parse_cursor(cursor: str) -> tuple[datetime, UUID]:
    """
    Parse a cursor of the form "ts|uuid".

    We use the same cursor format as DMS/Leave for consistency.
    """

    try:
        ts_raw, id_raw = cursor.split("|", 1)
        ts = datetime.fromisoformat(ts_raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts, UUID(id_raw)
    except Exception as e:  # noqa: BLE001 - stable AppError for clients
        raise AppError(
            code="validation_error",
            message=f"invalid cursor: {cursor!r}",
            status_code=400,
        ) from e


@router.post("/me/profile-change-requests")
def submit_profile_change(
    payload: ProfileChangeCreateIn,
    ctx: AuthContext = Depends(require_profile_change_submit),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.create_profile_change_request(
        db,
        ctx=ctx,
        change_set=payload.change_set,
        idempotency_key=payload.idempotency_key,
    )
    return ok(ProfileChangeRequestOut(**row).model_dump())


@router.get("/me/profile-change-requests")
def list_my_profile_changes(
    status: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    ctx: AuthContext = Depends(require_profile_change_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cur = _parse_cursor(cursor) if cursor else None
    rows, next_cursor = _svc.list_my_requests(
        db,
        ctx=ctx,
        status=status,
        limit=limit,
        cursor=cur,
    )
    items = [ProfileChangeRequestOut(**r) for r in rows]
    return ok(
        ProfileChangeRequestListOut(items=items, next_cursor=next_cursor).model_dump()
    )


@router.post("/me/profile-change-requests/{request_id}/cancel")
def cancel_profile_change(
    request_id: UUID,
    ctx: AuthContext = Depends(require_profile_change_submit),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.cancel_my_request(db, ctx=ctx, request_id=request_id)
    out = ProfileChangeCancelOut(id=UUID(str(row["id"])), status=str(row["status"]))  # type: ignore[arg-type]
    return ok(out.model_dump())
