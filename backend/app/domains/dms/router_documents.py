from __future__ import annotations

"""
DMS document mutation endpoints (versioning + workflow verification request).
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.db.session import get_db
from app.domains.dms.policies import (
    require_dms_document_verify,
    require_dms_document_write,
)
from app.domains.dms.schemas import DocumentAddVersionIn, DocumentOut, VerifyRequestOut
from app.domains.dms.service_documents import DmsDocumentService
from app.shared.types import AuthContext


router = APIRouter(prefix="/dms", tags=["dms"])
_svc = DmsDocumentService()


@router.post("/documents/{document_id}/versions")
def add_document_version(
    document_id: UUID,
    payload: DocumentAddVersionIn,
    ctx: AuthContext = Depends(require_dms_document_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.add_document_version(
        db,
        ctx=ctx,
        document_id=document_id,
        file_id=payload.file_id,
        notes=payload.notes,
    )
    return ok(DocumentOut(**row).model_dump())


@router.post("/documents/{document_id}/verify-request")
def create_verify_request(
    document_id: UUID,
    ctx: AuthContext = Depends(require_dms_document_verify),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    wf_request_id = _svc.create_verification_request(
        db, ctx=ctx, document_id=document_id
    )
    return ok(VerifyRequestOut(workflow_request_id=wf_request_id).model_dump())
