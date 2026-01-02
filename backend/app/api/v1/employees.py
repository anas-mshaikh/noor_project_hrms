"""
employees.py

This gives you:
- Create/list employees
- Upload face images => store pgvector embeddings (stub embedding for now)
- Search employees by face image (pgvector nearest-neighbor)
"""

from __future__ import annotations
import hashlib
import random
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
from app.models.models import Employee, EmployeeFace, Store
from app.worker.face_embedder import (
    FaceEmbedderError,
    get_face_embedder,
    read_image_bgr,
)

router = APIRouter(tags=["employees"])

# NOTE: must match models.py Vector(512)
# can later make this dynamic on the admin side
EMBEDDING_DIM = 512
ALLOWED_FACE_EXTS = {".jpg", ".jpeg", ".png"}


def _safe_ext(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return ext if ext in ALLOWED_FACE_EXTS else ".jpg"


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


class EmployeeCreateRequest(BaseModel):
    name: str
    employee_code: str


class EmployeeOut(BaseModel):
    id: UUID
    store_id: UUID
    name: str
    employee_code: str
    is_active: bool
    created_at: datetime


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

    emp = Employee(store_id=store_id, name=body.name, employee_code=body.employee_code)
    db.add(emp)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="employee_code already exists for this store"
        )

    db.refresh(emp)
    return EmployeeOut(
        id=emp.id,
        store_id=emp.store_id,
        name=emp.name,
        employee_code=emp.employee_code,
        is_active=emp.is_active,
        created_at=emp.created_at,
    )


@router.get("/stores/{store_id}/employees", response_model=list[EmployeeOut])
def list_employees(store_id: UUID, db: Session = Depends(get_db)) -> list[EmployeeOut]:
    rows = (
        db.query(Employee)
        .filter(Employee.store_id == store_id)
        .order_by(Employee.employee_code.asc())
        .all()
    )
    return [
        EmployeeOut(
            id=e.id,
            store_id=e.store_id,
            name=e.name,
            employee_code=e.employee_code,
            is_active=e.is_active,
            created_at=e.created_at,
        )
        for e in rows
    ]


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

    # Load face model once for this request.
    try:
        embedder = get_face_embedder()
    except FaceEmbedderError as e:
        raise HTTPException(status_code=500, detail=str(e))

    created: list[FaceCreatedOut] = []

    for f in files:
        face_id = uuid4()
        ext = _safe_ext(f.filename or "face.jpg")

        # Keep faces under data_dir/faces/<employee_id>/<face_id>.jpg
        rel_path = f"faces/{employee_id}/{face_id}{ext}"
        abs_path = Path(settings.data_dir) / rel_path

        _bytes, sha = _save_upload_and_sha256(f, abs_path)

        # Read + embed
        try:
            img = read_image_bgr(abs_path)
            face = embedder.embed_single_face(img)
        except FaceEmbedderError as e:
            # Client issue (bad image), so 400
            raise HTTPException(status_code=400, detail=str(e))

        if len(face.embedding) != EMBEDDING_DIM:
            raise HTTPException(
                status_code=500,
                detail=f"Embedding dim mismatch: expected {EMBEDDING_DIM}, got {len(face.embedding)}",
            )

        row = EmployeeFace(
            id=face_id,
            employee_id=employee_id,
            embedding=face.embedding,
            snapshot_path=rel_path,  # store the uploaded image path
            quality_score=face.quality_score,
            model_version=face.model_version,
        )
        db.add(row)
        db.commit()

        created.append(
            FaceCreatedOut(
                face_id=face_id,
                employee_id=employee_id,
                snapshot_path=rel_path,
                model_version=face.model_version,
            )
        )
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
        embedder = get_face_embedder()
    except FaceEmbedderError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Save the query image too (optional but nice for debugging)
    query_id = uuid4()
    rel_path = f"faces/_queries/{query_id}{ext}"
    abs_path = Path(settings.data_dir) / rel_path

    _bytes, sha = _save_upload_and_sha256(file, abs_path)

    try:
        img = read_image_bgr(abs_path)
        face = embedder.embed_best_face(img)
    except FaceEmbedderError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if face is None:
        raise HTTPException(status_code=400, detail="No face detected in query image")

    # Min cosine distance per employee (because each employee has many face templates)
    dist_expr = EmployeeFace.embedding.cosine_distance(face.embedding)

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
