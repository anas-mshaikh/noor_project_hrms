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

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Camera
from app.models.models import Store
from app.models.models import Video
from app.worker.zones import ZoneConfig, validate_zone_config

router = APIRouter(tags=["cameras"])


class CalibrationValidateOut(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str]


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


@router.post(
    "/cameras/{camera_id}/calibration/validate", response_model=CalibrationValidateOut
)
def validate_camera_calibration(
    camera_id: UUID,
    video_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> CalibrationValidateOut:
    cam = db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    target_w = target_h = None
    if video_id is not None:
        v = db.get(Video, video_id)
        if v is None:
            raise HTTPException(status_code=404, detail="Video not found")
        if v.camera_id != camera_id:
            raise HTTPException(
                status_code=400, detail="video_id does not belong to this camera"
            )
        target_w, target_h = v.width, v.height

    try:
        cfg = ZoneConfig.from_calibration_json(
            cam.calibration_json or {},
            target_width=target_w,
            target_height=target_h,
        )
    except ValueError as e:
        return CalibrationValidateOut(ok=False, errors=[str(e)], warnings=[])

    errors, warnings = validate_zone_config(cfg)
    return CalibrationValidateOut(
        ok=(len(errors) == 0), errors=errors, warnings=warnings
    )
