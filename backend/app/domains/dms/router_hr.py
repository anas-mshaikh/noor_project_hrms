"""
HR endpoints for employee document library.

Routes are under `/hr/...` to match existing HR domain conventions:
- POST /api/v1/hr/employees/{employee_id}/documents
- GET  /api/v1/hr/employees/{employee_id}/documents
"""

from __future__ import annotations


from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.dms.policies import (
    require_dms_document_read,
    require_dms_document_write,
)
from app.domains.dms.schemas import (
    DocumentListOut,
    DocumentOut,
    EmployeeDocumentCreateIn,
)
from app.domains.dms.service_documents import DmsDocumentService
from app.shared.types import AuthContext


router = APIRouter(prefix="/hr", tags=["dms"])
_svc = DmsDocumentService()


def _parse_cursor(cursor: str) -> tuple[datetime, UUID]:
    """
    Parse a cursor in the "ts|uuid" format used across the repo.
    """

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


@router.post("/employees/{employee_id}/documents")
def create_employee_document(
    employee_id: UUID,
    payload: EmployeeDocumentCreateIn,
    ctx: AuthContext = Depends(require_dms_document_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.create_employee_document(
        db,
        ctx=ctx,
        employee_id=employee_id,
        document_type_code=payload.document_type_code,
        file_id=payload.file_id,
        expires_at=payload.expires_at,
        notes=payload.notes,
    )
    return ok(DocumentOut(**row).model_dump())


@router.get("/employees/{employee_id}/documents")
def list_employee_documents(
    employee_id: UUID,
    status: str | None = Query(default=None),
    type: str | None = Query(default=None, alias="type"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    ctx: AuthContext = Depends(require_dms_document_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cur = _parse_cursor(cursor) if cursor else None
    rows, next_cursor = _svc.list_employee_documents_hr(
        db,
        ctx=ctx,
        employee_id=employee_id,
        status=status,
        type_code=type,
        limit=limit,
        cursor=cur,
    )
    items = [DocumentOut(**r) for r in rows]
    return ok(DocumentListOut(items=items, next_cursor=next_cursor).model_dump())
