"""
DMS file endpoints.

Endpoints:
- POST /api/v1/dms/files              (multipart upload)
- GET  /api/v1/dms/files/{file_id}    (metadata, enveloped)
- GET  /api/v1/dms/files/{file_id}/download (bytes)

Notes:
- JSON endpoints use the standard envelope.
- Download returns a FileResponse (bytes); errors are still JSON via AppError.
"""

from __future__ import annotations


from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.db.session import get_db
from app.domains.dms.policies import require_dms_file_read, require_dms_file_write
from app.domains.dms.schemas import DmsFileOut
from app.domains.dms.service_files import DmsFileService
from app.shared.types import AuthContext


router = APIRouter(prefix="/dms", tags=["dms"])
_svc = DmsFileService()


@router.post("/files")
def upload_file(
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(require_dms_file_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.upload_file(db, ctx=ctx, upload_file=file)
    return ok(DmsFileOut(**row).model_dump())


@router.get("/files/{file_id}")
def get_file_meta(
    file_id: UUID,
    ctx: AuthContext = Depends(require_dms_file_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.get_file_meta(db, ctx=ctx, file_id=file_id)
    return ok(DmsFileOut(**row).model_dump())


@router.get("/files/{file_id}/download")
def download_file(
    file_id: UUID,
    ctx: AuthContext = Depends(require_dms_file_read),
    db: Session = Depends(get_db),
) -> FileResponse:
    return _svc.download_file_response(db, ctx=ctx, file_id=file_id)
