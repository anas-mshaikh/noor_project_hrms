"""
employees.py

This gives you:
- Create/list employees
- Upload face images => store pgvector embeddings (ArcFace ONNX)
- Search employees by face image (pgvector nearest-neighbor)
"""

from __future__ import annotations
import hashlib
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.employees.schemas import EmployeeCreateRequest, EmployeeOut
from app.employees.service import create_employee_in_db
from app.face_system.detector.opencv_yn import FaceSystemModelError
from app.face_system.runtime_processor import get_runtime_processor
from app.models.models import Employee, EmployeeFace, Store

router = APIRouter(tags=["employees"])

# NOTE: must match models.py Vector(512)
# can later make this dynamic on the admin side
EMBEDDING_DIM = 512
ALLOWED_FACE_EXTS = {".jpg", ".jpeg", ".png"}


def _safe_ext(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return ext if ext in ALLOWED_FACE_EXTS else ".jpg"


def _read_image_bgr(path: Path):
    """
    Read an image from disk into a BGR numpy array (OpenCV convention).
    """
    try:
        import cv2  # type: ignore
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="opencv-python is required to decode images",
        ) from e

    img = cv2.imread(str(path))
    if img is None:
        raise HTTPException(status_code=400, detail=f"could not read image: {path.name}")
    return img


def _save_upload_and_sha256(upload: UploadFile, dest: Path) -> tuple[int, str]:
    """
    Stream upload to disk AND compute sha256 in one pass.
    Returns (bytes_written, sha256_hex).

    We store images on disk so:
    - you can audit what was enrolled
    - you can debug recognition issues later
    """
    h = hashlib.sha256()
    dest.parent.mkdir(parents=True, exist_ok=True)

    tmp = dest.with_suffix(dest.suffix + ".part")
    size = 0
    try:
        with tmp.open("wb") as out:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                size += len(chunk)
        tmp.replace(dest)
        return size, h.hexdigest()
    finally:
        upload.file.close()


@router.post(
    "/stores/{store_id}/employees",
    response_model=EmployeeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    store_id: UUID, body: EmployeeCreateRequest, db: Session = Depends(get_db)
) -> EmployeeOut:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    try:
        emp = create_employee_in_db(db, store_id=store_id, body=body)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="employee_code already exists for this store"
        )

    db.refresh(emp)
    return EmployeeOut.model_validate(emp, from_attributes=True)


@router.get("/stores/{store_id}/employees", response_model=list[EmployeeOut])
def list_employees(store_id: UUID, db: Session = Depends(get_db)) -> list[EmployeeOut]:
    rows = (
        db.query(Employee)
        .filter(Employee.store_id == store_id)
        .order_by(Employee.employee_code.asc())
        .all()
    )
    return [EmployeeOut.model_validate(e, from_attributes=True) for e in rows]


class FaceCreatedOut(BaseModel):
    face_id: UUID
    employee_id: UUID
    snapshot_path: str
    model_version: str


@router.post("/employees/{employee_id}/faces", response_model=list[FaceCreatedOut])
def upload_employee_faces(
    employee_id: UUID,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> list[FaceCreatedOut]:
    """
    Upload 1..N face images and store embeddings in pgvector.

    Enrollment rules:
    - Each image MUST contain exactly one face (to avoid enrolling the wrong person).
    - Store multiple templates per employee (5–20 is a good target).
    """
    emp = db.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Reuse one cached processor per store (loads models once).
    try:
        proc = get_runtime_processor(store_id=emp.store_id, camera_id=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    created: list[FaceCreatedOut] = []

    for f in files:
        face_id = uuid4()
        ext = _safe_ext(f.filename or "face.jpg")

        # File-based training library path (Frigate-style):
        #   data/faces/<store_id>/<employee_id>/<face_id>.<ext>
        #
        # We store the FACE CROP (not the full original upload) so the prototype
        # builder can embed quickly without re-running face detection.
        rel_path = f"faces/{emp.store_id}/{employee_id}/{face_id}{ext}"
        abs_path = Path(settings.data_dir) / rel_path

        _bytes, _sha = _save_upload_and_sha256(f, abs_path)

        # Detect + crop face (strict: exactly one face to avoid wrong enrollment).
        img = _read_image_bgr(abs_path)
        try:
            dets = proc.detector.detect(img)
        except FaceSystemModelError as e:
            raise HTTPException(status_code=500, detail=str(e))
        if not dets:
            raise HTTPException(status_code=400, detail="No face detected in image")
        if len(dets) > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Multiple faces detected ({len(dets)}). Upload a single-person face image.",
            )
        det = dets[0]

        x1, y1, x2, y2 = det.bbox_xyxy
        face_crop = img[y1:y2, x1:x2].copy()
        if face_crop.size == 0:
            raise HTTPException(status_code=400, detail="Invalid face crop")

        # Align (Frigate-style) if available; fall back to raw crop if model isn't present.
        aligned = proc.aligner.align(face_crop) or face_crop

        # Embed (ArcFace-style ONNX).
        try:
            emb = proc.embedder.embed(aligned).astype(float).tolist()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        if len(emb) != EMBEDDING_DIM:
            raise HTTPException(
                status_code=500,
                detail=f"Embedding dim mismatch: expected {EMBEDDING_DIM}, got {len(emb)}",
            )

        # Overwrite the stored file with the extracted face crop.
        # This keeps the on-disk training library consistent and fast to load.
        try:
            import cv2  # type: ignore

            cv2.imwrite(str(abs_path), face_crop)
        except Exception:
            pass

        # Simple quality score (0..1): size + blur (used only for UI/debug).
        try:
            import cv2  # type: ignore

            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
            blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            fh, fw = face_crop.shape[:2]
            area = float(fh * fw)
            size_score = min(1.0, area / float(80.0 * 80.0))
            blur_score = min(1.0, blur / 150.0)
            quality_score = float(size_score * blur_score)
        except Exception:
            quality_score = 0.0

        row = EmployeeFace(
            id=face_id,
            employee_id=employee_id,
            embedding=emb,
            snapshot_path=rel_path,  # store the uploaded image path
            quality_score=quality_score,
            model_version=f"onnx:{Path(proc.cfg.embedder.model_path).name}",
        )
        db.add(row)
        db.commit()

        created.append(
            FaceCreatedOut(
                face_id=face_id,
                employee_id=employee_id,
                snapshot_path=rel_path,
                model_version=f"onnx:{Path(proc.cfg.embedder.model_path).name}",
            )
        )

    # Clear prototypes so they rebuild with the newly enrolled faces.
    proc.recognizer.clear()

    return created


class FaceSearchMatchOut(BaseModel):
    employee_id: UUID
    employee_code: str
    employee_name: str
    cosine_distance: float
    confidence: float


@router.post(
    "/stores/{store_id}/employees/search/by-face",
    response_model=list[FaceSearchMatchOut],
)
def search_employee_by_face(
    store_id: UUID,
    file: UploadFile = File(...),
    limit: int = 5,
    db: Session = Depends(get_db),
) -> list[FaceSearchMatchOut]:
    """
    Upload a face image and return nearest employees using pgvector.

    Search rules:
    - We pick the "best/largest" face if multiple faces are in the query image.
    """
    limit = max(1, min(int(limit), 20))
    ext = _safe_ext(file.filename or "query.jpg")

    try:
        proc = get_runtime_processor(store_id=store_id, camera_id=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Save the query image too (optional but nice for debugging)
    query_id = uuid4()
    rel_path = f"faces/_queries/{query_id}{ext}"
    abs_path = Path(settings.data_dir) / rel_path

    _bytes, sha = _save_upload_and_sha256(file, abs_path)

    img = _read_image_bgr(abs_path)
    try:
        det = proc.detector.detect_best(img)
    except FaceSystemModelError as e:
        raise HTTPException(status_code=500, detail=str(e))
    if det is None:
        raise HTTPException(status_code=400, detail="No face detected in query image")

    x1, y1, x2, y2 = det.bbox_xyxy
    face_crop = img[y1:y2, x1:x2].copy()
    if face_crop.size == 0:
        raise HTTPException(status_code=400, detail="Invalid face crop")

    aligned = proc.aligner.align(face_crop) or face_crop
    try:
        emb = proc.embedder.embed(aligned).astype(float).tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Min cosine distance per employee (because each employee has many face templates)
    dist_expr = EmployeeFace.embedding.cosine_distance(emb)

    subq = (
        db.query(
            EmployeeFace.employee_id.label("employee_id"),
            sa.func.min(dist_expr).label("distance"),
        )
        .join(Employee, Employee.id == EmployeeFace.employee_id)
        .filter(Employee.store_id == store_id, Employee.is_active.is_(True))
        .group_by(EmployeeFace.employee_id)
        .subquery()
    )

    rows = (
        db.query(Employee, subq.c.distance)
        .join(subq, subq.c.employee_id == Employee.id)
        .order_by(subq.c.distance.asc())
        .limit(limit)
        .all()
    )

    out: list[FaceSearchMatchOut] = []
    for emp, dist in rows:
        dist_f = float(dist)

        # UI-friendly confidence mapping (tune later)
        confidence = max(0.0, 1.0 - dist_f)

        out.append(
            FaceSearchMatchOut(
                employee_id=emp.id,
                employee_code=emp.employee_code,
                employee_name=emp.name,
                cosine_distance=dist_f,
                confidence=confidence,
            )
        )

    return out
