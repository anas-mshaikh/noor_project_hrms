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
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

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
from app.models.models import Employee

router = APIRouter(prefix="", tags=["face"])


def _read_upload_image_bgr(file: UploadFile) -> np.ndarray:
    """
    Decode UploadFile into BGR numpy image.
    """
    try:
        import cv2  # type: ignore
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="opencv-python is required to decode images",
        ) from e

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")

    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="could not decode image")
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
    store_id: UUID
    employees: list[EmployeeFacesOut]


@router.get("/stores/{store_id}/faces", response_model=FaceLibraryOut)
def list_faces(store_id: UUID, db: Session = Depends(get_db)) -> FaceLibraryOut:
    """
    List training images per employee for a store.
    """
    cfg = FaceSystemConfig.from_settings()
    storage = FaceLibraryStorage(cfg.storage)

    emps = (
        db.query(Employee)
        .filter(Employee.store_id == store_id, Employee.is_active.is_(True))
        .order_by(Employee.employee_code.asc())
        .all()
    )

    out_emps: list[EmployeeFacesOut] = []
    for e in emps:
        imgs = storage.list_employee_images(store_id=store_id, employee_id=e.id)
        out_emps.append(
            EmployeeFacesOut(
                employee_id=e.id,
                employee_code=e.employee_code,
                employee_name=e.name,
                images=[FaceImageOut(filename=i.filename, rel_path=i.rel_path) for i in imgs],
            )
        )

    return FaceLibraryOut(store_id=store_id, employees=out_emps)


class FaceRegisterResponse(BaseModel):
    employee_id: UUID
    stored: FaceImageOut


@router.post("/employees/{employee_id}/faces/register", response_model=FaceRegisterResponse)
def register_face(
    employee_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> FaceRegisterResponse:
    """
    Register a training image for an employee.

    Behavior:
    - Detect best face in the uploaded image
    - Crop the face
    - Save to <FACE_DIR>/<store_id>/<employee_id>/<timestamp>.jpg
    - Clear prototypes (they will rebuild on next recognition)
    """
    emp = db.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="employee not found")

    cfg = FaceSystemConfig.from_settings()
    storage = FaceLibraryStorage(cfg.storage)

    # Use the same detector as runtime (for consistent crops).
    try:
        proc = get_runtime_processor(store_id=emp.store_id, camera_id=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    img = _read_upload_image_bgr(file)

    try:
        det = proc.detector.detect_best(img)
    except FaceDetectorModelError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if det is None:
        raise HTTPException(status_code=400, detail="no face detected")

    x1, y1, x2, y2 = det.bbox_xyxy
    face_crop = img[y1:y2, x1:x2].copy()
    if face_crop.size == 0:
        raise HTTPException(status_code=400, detail="invalid face crop")

    stored = storage.save_face_crop(
        store_id=emp.store_id,
        employee_id=emp.id,
        face_crop_bgr=face_crop,
        ext=Path(file.filename or "face.jpg").suffix or ".jpg",
    )

    # Clear prototypes so they rebuild with the new image.
    proc.recognizer.clear()

    return FaceRegisterResponse(
        employee_id=emp.id,
        stored=FaceImageOut(filename=stored.filename, rel_path=stored.rel_path),
    )


class FaceRecognizeRequestOut(BaseModel):
    employee_id: UUID | None
    confidence: float
    cosine_similarity: float | None
    top_k: list[dict[str, Any]]


@router.post("/stores/{store_id}/faces/recognize", response_model=FaceRecognizeRequestOut)
def recognize_face(
    store_id: UUID,
    file: UploadFile = File(...),
    top_k: int = 5,
) -> FaceRecognizeRequestOut:
    """
    Recognize a face image against current store prototypes.
    """
    try:
        proc = get_runtime_processor(store_id=store_id, camera_id=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    img = _read_upload_image_bgr(file)

    try:
        result = proc.recognizer.recognize_image(img, top_k=top_k)
    except (FaceDetectorModelError, FaceAlignerModelError, FaceEmbedderModelError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except FaceSystemError as e:
        # User-correctable issues (no prototypes, no face detected, etc.)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return FaceRecognizeRequestOut(
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
    )


class FaceClearResponse(BaseModel):
    store_id: UUID
    cleared: bool


@router.post("/stores/{store_id}/faces/clear", response_model=FaceClearResponse)
def clear_prototypes(store_id: UUID) -> FaceClearResponse:
    """
    Clear in-memory prototypes for a store.
    """
    try:
        proc = get_runtime_processor(store_id=store_id, camera_id=None)
        proc.recognizer.clear()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return FaceClearResponse(store_id=store_id, cleared=True)


class FaceRebuildResponse(BaseModel):
    store_id: UUID
    started: bool


@router.post("/stores/{store_id}/faces/rebuild", response_model=FaceRebuildResponse)
def rebuild_prototypes(store_id: UUID) -> FaceRebuildResponse:
    """
    Trigger an async prototype rebuild for a store.
    """
    try:
        proc = get_runtime_processor(store_id=store_id, camera_id=None)
        proc.recognizer.trigger_rebuild_async()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return FaceRebuildResponse(store_id=store_id, started=True)


class FaceDeleteResponse(BaseModel):
    employee_id: UUID
    deleted: bool


@router.delete(
    "/employees/{employee_id}/faces/{filename}",
    response_model=FaceDeleteResponse,
)
def delete_training_image(
    employee_id: UUID,
    filename: str,
    db: Session = Depends(get_db),
) -> FaceDeleteResponse:
    """
    Delete one training image for an employee.
    """
    emp = db.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="employee not found")

    cfg = FaceSystemConfig.from_settings()
    storage = FaceLibraryStorage(cfg.storage)

    deleted = storage.delete_employee_image(
        store_id=emp.store_id, employee_id=emp.id, filename=filename
    )

    # Clear prototypes so next recognition rebuilds without the deleted image.
    try:
        proc = get_runtime_processor(store_id=emp.store_id, camera_id=None)
        proc.recognizer.clear()
    except Exception:
        # Deletion should succeed even if the face system can't initialize (missing models).
        pass

    return FaceDeleteResponse(employee_id=emp.id, deleted=bool(deleted))
