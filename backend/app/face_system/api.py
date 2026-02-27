"""
api.py

FastAPI endpoints for the Frigate-style face subsystem.

These endpoints are designed for admin/debug flows:
- Register training images per employee (file-based library)
- List/delete training images
- Rebuild/clear in-memory prototypes
- Recognize a face image against current prototypes
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.auth.deps import require_permission
from app.auth.permissions import FACE_LIBRARY_READ, FACE_LIBRARY_WRITE, FACE_RECOGNIZE
from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.face_system.config import FaceSystemConfig
from app.face_system.aligners.opencv_lbf import FaceSystemModelError as FaceAlignerModelError
from app.face_system.detector.opencv_yn import FaceSystemModelError as FaceDetectorModelError
from app.face_system.embedders.insightface_arcface import (
    FaceSystemModelError as FaceEmbedderModelError,
)
from app.face_system.recognizer import FaceSystemError
from app.face_system.runtime_processor import get_runtime_processor
from app.face_system.storage import FaceLibraryStorage, StoredFaceImage
from app.shared.types import AuthContext

router = APIRouter(prefix="", tags=["face"])


def _read_upload_image_bgr(file: UploadFile) -> np.ndarray:
    """
    Decode UploadFile into BGR numpy image.
    """
    try:
        import cv2  # type: ignore
    except Exception as e:
        raise AppError(
            code="face.model.unavailable",
            message="opencv-python is required to decode images",
            status_code=500,
        ) from e

    data = file.file.read()
    if not data:
        raise AppError(code="face.image.empty", message="empty file", status_code=400)

    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise AppError(code="face.image.decode_failed", message="could not decode image", status_code=400)
    return img


class FaceImageOut(BaseModel):
    filename: str
    rel_path: str


class EmployeeFacesOut(BaseModel):
    employee_id: UUID
    employee_code: str
    employee_name: str
    images: list[FaceImageOut]


class FaceLibraryOut(BaseModel):
    tenant_id: UUID
    branch_id: UUID
    employees: list[EmployeeFacesOut]

def _require_company_id(db: Session, *, tenant_id: UUID, branch_id: UUID) -> UUID:
    row = db.execute(
        sa.text(
            """
            SELECT company_id
            FROM tenancy.branches
            WHERE id = :branch_id
              AND tenant_id = :tenant_id
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    ).first()
    if row is None:
        raise AppError(code="face.branch.not_found", message="Branch not found", status_code=404)
    return row[0]


@router.get("/branches/{branch_id}/faces")
def list_faces(
    branch_id: UUID,
    ctx: AuthContext = Depends(require_permission(FACE_LIBRARY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    List training images per employee for a branch.
    """
    cfg = FaceSystemConfig.from_settings()
    storage = FaceLibraryStorage(cfg.storage)

    company_id = _require_company_id(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id)
    rows = db.execute(
        sa.text(
            """
            WITH current_employment AS (
              SELECT
                ee.employee_id,
                ee.branch_id,
                ROW_NUMBER() OVER (
                  PARTITION BY ee.employee_id
                  ORDER BY ee.is_primary DESC NULLS LAST, ee.start_date DESC, ee.id DESC
                ) AS rn
              FROM hr_core.employee_employment ee
              WHERE ee.tenant_id = :tenant_id
                AND ee.company_id = :company_id
                AND ee.end_date IS NULL
            ),
            ce AS (
              SELECT employee_id, branch_id
              FROM current_employment
              WHERE rn = 1
            )
            SELECT
              e.id AS employee_id,
              e.employee_code AS employee_code,
              p.first_name AS first_name,
              p.last_name AS last_name
            FROM ce
            JOIN hr_core.employees e ON e.id = ce.employee_id
            JOIN hr_core.persons p ON p.id = e.person_id
            WHERE e.tenant_id = :tenant_id
              AND e.company_id = :company_id
              AND ce.branch_id = :branch_id
              AND e.status = 'ACTIVE'
            ORDER BY e.employee_code ASC, e.id ASC
            """
        ),
        {"tenant_id": ctx.scope.tenant_id, "company_id": company_id, "branch_id": branch_id},
    ).all()

    out_emps: list[EmployeeFacesOut] = []
    for r in rows:
        emp_id = r.employee_id
        imgs = storage.list_employee_images(
            tenant_id=ctx.scope.tenant_id, branch_id=branch_id, employee_id=emp_id
        )
        full_name = f"{r.first_name} {r.last_name}".strip()
        out_emps.append(
            EmployeeFacesOut(
                employee_id=emp_id,
                employee_code=r.employee_code,
                employee_name=full_name,
                images=[FaceImageOut(filename=i.filename, rel_path=i.rel_path) for i in imgs],
            )
        )

    return ok(
        FaceLibraryOut(
            tenant_id=ctx.scope.tenant_id,
            branch_id=branch_id,
            employees=out_emps,
        ).model_dump()
    )


class FaceRegisterResponse(BaseModel):
    employee_id: UUID
    stored: FaceImageOut


@router.post("/branches/{branch_id}/employees/{employee_id}/faces/register")
def register_face(
    branch_id: UUID,
    employee_id: UUID,
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(require_permission(FACE_LIBRARY_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Register a training image for an employee.

    Behavior:
    - Detect best face in the uploaded image
    - Crop the face
    - Save to <FACE_DIR>/<tenant_id>/<branch_id>/<employee_id>/<timestamp>.jpg
    - Clear prototypes (they will rebuild on next recognition)
    """
    company_id = _require_company_id(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id)
    # Ensure employee exists in-tenant/company and has an active employment in this branch.
    row = db.execute(
        sa.text(
            """
            SELECT 1
            FROM hr_core.employees e
            JOIN hr_core.employee_employment ee ON ee.employee_id = e.id
            WHERE e.id = :employee_id
              AND e.tenant_id = :tenant_id
              AND e.company_id = :company_id
              AND ee.tenant_id = :tenant_id
              AND ee.company_id = :company_id
              AND ee.branch_id = :branch_id
              AND ee.end_date IS NULL
            LIMIT 1
            """
        ),
        {
            "employee_id": employee_id,
            "tenant_id": ctx.scope.tenant_id,
            "company_id": company_id,
            "branch_id": branch_id,
        },
    ).first()
    if row is None:
        raise AppError(code="face.employee.not_found", message="Employee not found", status_code=404)

    cfg = FaceSystemConfig.from_settings()
    storage = FaceLibraryStorage(cfg.storage)

    # Use the same detector as runtime (for consistent crops).
    try:
        proc = get_runtime_processor(tenant_id=ctx.scope.tenant_id, branch_id=branch_id, camera_id=None)
    except Exception as e:
        raise AppError(
            code="face.model.unavailable",
            message="Face system unavailable",
            status_code=500,
        ) from e

    img = _read_upload_image_bgr(file)

    try:
        det = proc.detector.detect_best(img)
    except FaceDetectorModelError as e:
        raise AppError(code="face.model.unavailable", message="Face system unavailable", status_code=500) from e

    if det is None:
        raise AppError(code="face.no_face_detected", message="no face detected", status_code=400)

    x1, y1, x2, y2 = det.bbox_xyxy
    face_crop = img[y1:y2, x1:x2].copy()
    if face_crop.size == 0:
        raise AppError(code="face.image.decode_failed", message="invalid face crop", status_code=400)

    stored = storage.save_face_crop(
        tenant_id=ctx.scope.tenant_id,
        branch_id=branch_id,
        employee_id=employee_id,
        face_crop_bgr=face_crop,
        ext=Path(file.filename or "face.jpg").suffix or ".jpg",
    )

    # Clear prototypes so they rebuild with the new image.
    proc.recognizer.clear()

    return ok(
        FaceRegisterResponse(
            employee_id=employee_id,
            stored=FaceImageOut(filename=stored.filename, rel_path=stored.rel_path),
        ).model_dump()
    )


class FaceRecognizeRequestOut(BaseModel):
    employee_id: UUID | None
    confidence: float
    cosine_similarity: float | None
    top_k: list[dict[str, Any]]


@router.post("/branches/{branch_id}/faces/recognize")
def recognize_face(
    branch_id: UUID,
    file: UploadFile = File(...),
    top_k: int = 5,
    ctx: AuthContext = Depends(require_permission(FACE_RECOGNIZE)),
) -> dict[str, object]:
    """
    Recognize a face image against current branch prototypes.
    """
    try:
        proc = get_runtime_processor(tenant_id=ctx.scope.tenant_id, branch_id=branch_id, camera_id=None)
    except Exception as e:
        raise AppError(code="face.model.unavailable", message="Face system unavailable", status_code=500) from e

    img = _read_upload_image_bgr(file)

    try:
        result = proc.recognizer.recognize_image(img, top_k=top_k)
    except (FaceDetectorModelError, FaceAlignerModelError, FaceEmbedderModelError) as e:
        raise AppError(code="face.model.unavailable", message="Face system unavailable", status_code=500) from e
    except FaceSystemError as e:
        # User-correctable issues (no prototypes, no face detected, etc.)
        raise AppError(code="face.recognition.failed", message=str(e), status_code=400) from e
    except Exception as e:
        raise AppError(code="face.model.unavailable", message="Face system unavailable", status_code=500) from e

    return ok(
        FaceRecognizeRequestOut(
            employee_id=result.employee_id,
            confidence=float(result.confidence),
            cosine_similarity=float(result.cosine_similarity) if result.cosine_similarity is not None else None,
            top_k=[
                {
                    "employee_id": m.employee_id,
                    "cosine_similarity": float(m.cosine_similarity),
                    "confidence": float(m.confidence),
                }
                for m in result.top_k
            ],
        ).model_dump()
    )


class FaceClearResponse(BaseModel):
    tenant_id: UUID
    branch_id: UUID
    cleared: bool


@router.post("/branches/{branch_id}/faces/clear")
def clear_prototypes(
    branch_id: UUID,
    ctx: AuthContext = Depends(require_permission(FACE_LIBRARY_WRITE)),
) -> dict[str, object]:
    """
    Clear in-memory prototypes for a store.
    """
    try:
        proc = get_runtime_processor(tenant_id=ctx.scope.tenant_id, branch_id=branch_id, camera_id=None)
        proc.recognizer.clear()
    except Exception as e:
        raise AppError(code="face.model.unavailable", message="Face system unavailable", status_code=500) from e
    return ok(
        FaceClearResponse(tenant_id=ctx.scope.tenant_id, branch_id=branch_id, cleared=True).model_dump()
    )


class FaceRebuildResponse(BaseModel):
    tenant_id: UUID
    branch_id: UUID
    started: bool


@router.post("/branches/{branch_id}/faces/rebuild")
def rebuild_prototypes(
    branch_id: UUID,
    ctx: AuthContext = Depends(require_permission(FACE_LIBRARY_WRITE)),
) -> dict[str, object]:
    """
    Trigger an async prototype rebuild for a store.
    """
    try:
        proc = get_runtime_processor(tenant_id=ctx.scope.tenant_id, branch_id=branch_id, camera_id=None)
        proc.recognizer.trigger_rebuild_async()
    except Exception as e:
        raise AppError(code="face.model.unavailable", message="Face system unavailable", status_code=500) from e
    return ok(
        FaceRebuildResponse(tenant_id=ctx.scope.tenant_id, branch_id=branch_id, started=True).model_dump()
    )


class FaceDeleteResponse(BaseModel):
    employee_id: UUID
    deleted: bool


@router.delete(
    "/branches/{branch_id}/employees/{employee_id}/faces/{filename}",
)
def delete_training_image(
    branch_id: UUID,
    employee_id: UUID,
    filename: str,
    ctx: AuthContext = Depends(require_permission(FACE_LIBRARY_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Delete one training image for an employee.
    """
    company_id = _require_company_id(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id)
    row = db.execute(
        sa.text(
            """
            SELECT 1
            FROM hr_core.employees e
            JOIN hr_core.employee_employment ee ON ee.employee_id = e.id
            WHERE e.id = :employee_id
              AND e.tenant_id = :tenant_id
              AND e.company_id = :company_id
              AND ee.tenant_id = :tenant_id
              AND ee.company_id = :company_id
              AND ee.branch_id = :branch_id
              AND ee.end_date IS NULL
            LIMIT 1
            """
        ),
        {
            "employee_id": employee_id,
            "tenant_id": ctx.scope.tenant_id,
            "company_id": company_id,
            "branch_id": branch_id,
        },
    ).first()
    if row is None:
        raise AppError(code="face.employee.not_found", message="Employee not found", status_code=404)

    cfg = FaceSystemConfig.from_settings()
    storage = FaceLibraryStorage(cfg.storage)

    deleted = storage.delete_employee_image(
        tenant_id=ctx.scope.tenant_id,
        branch_id=branch_id,
        employee_id=employee_id,
        filename=filename,
    )

    # Clear prototypes so next recognition rebuilds without the deleted image.
    try:
        proc = get_runtime_processor(tenant_id=ctx.scope.tenant_id, branch_id=branch_id, camera_id=None)
        proc.recognizer.clear()
    except Exception:
        # Deletion should succeed even if the face system can't initialize (missing models).
        pass

    return ok(FaceDeleteResponse(employee_id=employee_id, deleted=bool(deleted)).model_dump())
