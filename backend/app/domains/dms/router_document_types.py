from __future__ import annotations

"""
DMS document type endpoints (tenant-scoped catalog).
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.db.session import get_db
from app.domains.dms.policies import (
    require_dms_document_type_read,
    require_dms_document_type_write,
)
from app.domains.dms.schemas import (
    DocumentTypeCreateIn,
    DocumentTypeOut,
    DocumentTypePatchIn,
    DocumentTypesOut,
)
from app.domains.dms.service_documents import DmsDocumentService
from app.shared.types import AuthContext


router = APIRouter(prefix="/dms", tags=["dms"])
_svc = DmsDocumentService()


@router.get("/document-types")
def list_document_types(
    ctx: AuthContext = Depends(require_dms_document_type_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _svc.list_document_types(db, ctx=ctx)
    items = [DocumentTypeOut(**r) for r in rows]
    return ok(DocumentTypesOut(items=items).model_dump())


@router.post("/document-types")
def create_document_type(
    payload: DocumentTypeCreateIn,
    ctx: AuthContext = Depends(require_dms_document_type_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.create_document_type(
        db,
        ctx=ctx,
        code=payload.code,
        name=payload.name,
        requires_expiry=payload.requires_expiry,
        is_active=payload.is_active,
    )
    return ok(DocumentTypeOut(**row).model_dump())


@router.patch("/document-types/{doc_type_id}")
def patch_document_type(
    doc_type_id: UUID,
    payload: DocumentTypePatchIn,
    ctx: AuthContext = Depends(require_dms_document_type_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.patch_document_type(
        db,
        ctx=ctx,
        doc_type_id=doc_type_id,
        name=payload.name,
        requires_expiry=payload.requires_expiry,
        is_active=payload.is_active,
    )
    return ok(DocumentTypeOut(**row).model_dump())
