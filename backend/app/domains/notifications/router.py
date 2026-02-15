from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.deps import require_permission
from app.auth.permissions import NOTIFICATIONS_READ
from app.core.responses import ok
from app.db.session import get_db
from app.domains.notifications.schemas import NotificationListOut, NotificationOut, UnreadCountOut
from app.shared.types import AuthContext


router = APIRouter(prefix="/notifications", tags=["notifications"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        ts_raw, id_raw = cursor.split("|", 1)
        ts = datetime.fromisoformat(ts_raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts, UUID(id_raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid cursor: {cursor!r}") from e


@router.get("")
def list_notifications(
    unread_only: int = Query(0, ge=0, le=1),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    ctx: AuthContext = Depends(require_permission(NOTIFICATIONS_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cursor_ts: datetime | None = None
    cursor_id: UUID | None = None
    if cursor:
        cursor_ts, cursor_id = _parse_cursor(cursor)

    rows = db.execute(
        sa.text(
            """
            SELECT
              id,
              type,
              title,
              body,
              entity_type,
              entity_id,
              action_url,
              payload,
              created_at,
              read_at
            FROM workflow.notifications
            WHERE tenant_id = :tenant_id
              AND recipient_user_id = :user_id
              AND (:unread_only = 0 OR read_at IS NULL)
              AND (
                CAST(:cursor_ts AS timestamptz) IS NULL
                OR (created_at, id) < (CAST(:cursor_ts AS timestamptz), CAST(:cursor_id AS uuid))
              )
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
            """
        ),
        {
            "tenant_id": ctx.scope.tenant_id,
            "user_id": ctx.user_id,
            "unread_only": int(unread_only),
            "cursor_ts": cursor_ts,
            "cursor_id": cursor_id,
            "limit": int(limit),
        },
    ).mappings().all()

    items: list[NotificationOut] = []
    for r in rows:
        items.append(
            NotificationOut(
                id=r["id"],
                type=str(r["type"]),
                title=str(r["title"]),
                body=str(r["body"]),
                entity_type=r["entity_type"],
                entity_id=r["entity_id"],
                action_url=r["action_url"],
                payload=r["payload"] or {},
                created_at=r["created_at"],
                read_at=r["read_at"],
            )
        )

    next_cursor: str | None = None
    if len(items) == int(limit):
        last = items[-1]
        next_cursor = f"{last.created_at.isoformat()}|{last.id}"

    payload = NotificationListOut(items=items, next_cursor=next_cursor)
    return ok(payload.model_dump())


@router.get("/unread-count")
def unread_count(
    ctx: AuthContext = Depends(require_permission(NOTIFICATIONS_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    count = int(
        db.execute(
            sa.text(
                """
                SELECT count(*)
                FROM workflow.notifications
                WHERE tenant_id = :tenant_id
                  AND recipient_user_id = :user_id
                  AND read_at IS NULL
                """
            ),
            {"tenant_id": ctx.scope.tenant_id, "user_id": ctx.user_id},
        ).scalar()
        or 0
    )
    return ok(UnreadCountOut(unread_count=count).model_dump())


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: UUID,
    ctx: AuthContext = Depends(require_permission(NOTIFICATIONS_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = db.execute(
        sa.text(
            """
            UPDATE workflow.notifications
            SET read_at = COALESCE(read_at, :now)
            WHERE id = :id
              AND tenant_id = :tenant_id
              AND recipient_user_id = :user_id
            RETURNING id, read_at
            """
        ),
        {
            "id": notification_id,
            "tenant_id": ctx.scope.tenant_id,
            "user_id": ctx.user_id,
            "now": _utcnow(),
        },
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification not found")

    db.commit()
    return ok({"id": str(row["id"]), "read_at": row["read_at"].isoformat() if row["read_at"] else None})


@router.post("/read-all")
def read_all(
    ctx: AuthContext = Depends(require_permission(NOTIFICATIONS_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    res = db.execute(
        sa.text(
            """
            UPDATE workflow.notifications
            SET read_at = :now
            WHERE tenant_id = :tenant_id
              AND recipient_user_id = :user_id
              AND read_at IS NULL
            """
        ),
        {"tenant_id": ctx.scope.tenant_id, "user_id": ctx.user_id, "now": _utcnow()},
    )
    db.commit()
    return ok({"updated": int(res.rowcount or 0)})
