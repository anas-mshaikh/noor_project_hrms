from __future__ import annotations

"""
ESS endpoints for "my documents" library.

Routes:
- GET /api/v1/ess/me/documents
- GET /api/v1/ess/me/documents/{document_id}
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.dms.policies import require_dms_document_read
from app.domains.dms.schemas import DocumentListOut, DocumentOut
from app.domains.dms.service_documents import DmsDocumentService
from app.shared.types import AuthContext


router = APIRouter(prefix="/ess", tags=["dms"])
_svc = DmsDocumentService()


def _parse_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        ts_raw, id_raw = cursor.split("|", 1)
        ts = datetime.fromisoformat(ts_raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts, UUID(id_raw)
    except Exception as e:
        raise AppError(
            code="validation_error",
            message=f"invalid cursor: {cursor!r}",
            status_code=400,
        ) from e


@router.get("/me/documents")
def list_my_documents(
    status: str | None = Query(default=None),
    type: str | None = Query(default=None, alias="type"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    ctx: AuthContext = Depends(require_dms_document_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cur = _parse_cursor(cursor) if cursor else None
    rows, next_cursor = _svc.list_my_documents_ess(
        db, ctx=ctx, status=status, type_code=type, limit=limit, cursor=cur
    )
    items = [DocumentOut(**r) for r in rows]
    return ok(DocumentListOut(items=items, next_cursor=next_cursor).model_dump())


@router.get("/me/documents/{document_id}")
def get_my_document(
    document_id: UUID,
    ctx: AuthContext = Depends(require_dms_document_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.get_my_document_ess(db, ctx=ctx, document_id=document_id)
    return ok(DocumentOut(**row).model_dump())
