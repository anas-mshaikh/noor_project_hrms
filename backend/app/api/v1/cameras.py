"""
cameras.py

Minimal endpoints to manage camera calibration_json.

We keep it intentionally flexible:
- Store the raw calibration_json as JSONB
- The worker parses it into ZoneConfig (zones.py)

Later you can add strong validation (Pydantic models for polygons/lines).
"""

from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Camera
from app.models.models import Store

router = APIRouter(tags=["cameras"])


class CameraCreateRequest(BaseModel):
    name: str
    placement: str | None = None
    calibration_json: dict[str, Any] | None = None


class CameraListOut(BaseModel):
    id: UUID
    store_id: UUID
    name: str
    placement: str | None
    calibration_json: dict[str, Any] | None
    created_at: datetime


@router.post(
    "/stores/{store_id}/cameras",
    response_model=CameraListOut,
    status_code=status.HTTP_201_CREATED,
)
def create_camera(
    store_id: UUID, body: CameraCreateRequest, db: Session = Depends(get_db)
) -> CameraListOut:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    cam = Camera(
        store_id=store_id,
        name=body.name,
        placement=body.placement,
        calibration_json=body.calibration_json,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)

    return CameraListOut(
        id=cam.id,
        store_id=cam.store_id,
        name=cam.name,
        placement=cam.placement,
        calibration_json=cam.calibration_json,
        created_at=cam.created_at,
    )


@router.get("/stores/{store_id}/cameras", response_model=list[CameraListOut])
def list_cameras(store_id: UUID, db: Session = Depends(get_db)) -> list[CameraListOut]:
    rows = (
        db.query(Camera)
        .filter(Camera.store_id == store_id)
        .order_by(Camera.created_at.asc())
        .all()
    )
    return [
        CameraListOut(
            id=c.id,
            store_id=c.store_id,
            name=c.name,
            placement=c.placement,
            calibration_json=c.calibration_json,
            created_at=c.created_at,
        )
        for c in rows
    ]


# TODO: Research on Frigate's camera/polygons mangement implementation
class CameraOut(BaseModel):
    id: UUID
    store_id: UUID
    name: str
    placement: str | None
    calibration_json: dict[str, Any] | None


class CalibrationUpdateRequest(BaseModel):
    calibration_json: dict[str, Any] = Field(
        ...,
        description=(
            "Raw camera calibration JSON. "
            "Expected fields are documented in app/worker/zones.py"
        ),
    )


@router.get("/cameras/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: UUID, db: Session = Depends(get_db)) -> CameraOut:
    cam = db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    return CameraOut(
        id=cam.id,
        store_id=cam.store_id,
        name=cam.name,
        placement=cam.placement,
        calibration_json=cam.calibration_json,
    )


@router.put("/cameras/{camera_id}/calibration", response_model=CameraOut)
def update_camera_calibration(
    camera_id: UUID,
    body: CalibrationUpdateRequest,
    db: Session = Depends(get_db),
) -> CameraOut:
    cam = db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    # We store whatever JSON you send; worker will interpret it.
    cam.calibration_json = body.calibration_json

    db.add(cam)
    db.commit()
    db.refresh(cam)

    return CameraOut(
        id=cam.id,
        store_id=cam.store_id,
        name=cam.name,
        placement=cam.placement,
        calibration_json=cam.calibration_json,
    )
