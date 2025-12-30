"""
cameras.py

Minimal endpoints to manage camera calibration_json.

We keep it intentionally flexible:
- Store the raw calibration_json as JSONB
- The worker parses it into ZoneConfig (zones.py)

Later you can add strong validation (Pydantic models for polygons/lines).
"""

from __future__ import annotations
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Camera

router = APIRouter(tags=["cameras"])


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
