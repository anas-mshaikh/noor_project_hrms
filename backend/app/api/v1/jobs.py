"""
POST /videos/{video_id}/jobs creates a processing run (worker integration is next step).
GET /jobs/{job_id} gives the UI polling endpoint.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Job, Video

router = APIRouter(tags=["jobs"])


class JobCreateRequest(BaseModel):
    config_overrides: dict[str, Any] = Field(default_factory=dict)


class JobCreateResponse(BaseModel):
    job_id: UUID
    status: str


class JobReadResponse(BaseModel):
    id: UUID
    video_id: UUID
    status: str
    progress: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@router.post(
    "/videos/{video_id}/jobs",
    response_model=JobCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_job(
    video_id: UUID, body: JobCreateRequest, db: Session = Depends(get_db)
) -> JobCreateResponse:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    job = Job(
        video_id=video_id,
        status="PENDING",
        config_json=body.config_overrides,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return JobCreateResponse(job_id=job.id, status=job.status)


@router.get("/jobs/{job_id}", response_model=JobReadResponse)
def get_job(job_id: UUID, db: Session = Depends(get_db)) -> JobReadResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobReadResponse(
        id=job.id,
        video_id=job.video_id,
        status=job.status,
        progress=job.progress,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
