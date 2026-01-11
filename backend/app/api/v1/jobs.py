"""
POST /videos/{video_id}/jobs creates + enqueues a processing run.
GET /jobs/{job_id} is the UI polling endpoint.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.face_system.runtime_processor import get_runtime_processor
from app.models.models import Event, Job, Track, Video
from app.queue.rq import DEFAULT_JOB_TIMEOUT_SEC, get_queue
from app.worker.tasks import process_video_job
from app.worker.rollup import (
    get_related_job_ids,
    get_store_day_context,
    recompute_attendance_for_store_day,
    recompute_metrics_hourly_for_job,
)
from app.worker.artifacts import write_job_artifacts


router = APIRouter(tags=["jobs"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# NOTE: tune this later
class JobRecomputeRequest(BaseModel):
    # Minimum confidence to attach an employee to an existing track snapshot.
    # This uses the face_system (prototype cosine similarity -> sigmoid confidence).
    min_confidence: float = 0.70
    recompute_rollups: bool = True
    rewrite_artifacts: bool = True


class JobRecomputeResponse(BaseModel):
    job_id: UUID
    assigned_tracks: int


def _assign_identities_for_job(
    db: Session, *, job_id: UUID, min_confidence: float
) -> int:
    """
    Re-assign identities for an existing job using the Frigate-style face system.

    This is useful when you:
    - enroll more training faces, then
    - want to attach employee_id to previously-unknown tracks/events.

    Implementation notes:
    - We rely on Track.best_snapshot_path (best face crop) produced by the pipeline.
    - We do not modify door logic; we only fill in employee_id where it was NULL.
    """
    try:
        import cv2  # type: ignore
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="opencv-python is required to decode snapshots for recompute",
        ) from e

    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    video = db.get(Video, job.video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found for job")

    # Load store prototypes (blocking build once).
    try:
        proc = get_runtime_processor(store_id=video.store_id, camera_id=None)
        proc.recognizer.ensure_built(block=True, timeout_sec=60.0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    assigned = 0
    tracks = db.query(Track).filter(Track.job_id == job_id).all()

    for t in tracks:
        # If the track already has an employee_id, ensure *all* events for that track
        # carry the same employee_id where they are still NULL.
        #
        # This repairs an edge-case where the pipeline inserts an Event before the
        # face system locks identity in the same frame (autoflush=False), so the
        # backfill UPDATE misses that just-inserted row.
        if t.employee_id is not None:
            (
                db.query(Event)
                .filter(
                    Event.job_id == job_id,
                    Event.track_key == t.track_key,
                    Event.employee_id.is_(None),
                )
                .update({Event.employee_id: t.employee_id}, synchronize_session=False)
            )
            continue

        if t.best_snapshot_path is None:
            continue

        img_path = (Path(settings.data_dir) / t.best_snapshot_path).resolve()
        if not img_path.exists():
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            continue

        try:
            result = proc.recognizer.recognize_image(img, top_k=5)
        except Exception:
            continue

        if result.employee_id is None:
            continue
        if float(result.confidence) < float(min_confidence):
            continue

        emp_id = result.employee_id

        t.employee_id = emp_id
        t.assigned_type = "employee"
        t.identity_confidence = float(result.confidence)
        db.add(t)

        # Update events for that track (do not overwrite non-null employee_id).
        (
            db.query(Event)
            .filter(
                Event.job_id == job_id,
                Event.track_key == t.track_key,
                Event.employee_id.is_(None),
            )
            .update({Event.employee_id: emp_id}, synchronize_session=False)
        )
        assigned += 1

    db.commit()
    return int(assigned)


class JobCreateRequest(BaseModel):
    config_overrides: dict[str, Any] = Field(default_factory=dict)


class JobCreateResponse(BaseModel):
    job_id: UUID
    status: str
    enqueued: bool
    queue_error: str | None = None


class JobReadResponse(BaseModel):
    id: UUID
    video_id: UUID
    status: str
    progress: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class JobActionResponse(BaseModel):
    job_id: UUID
    status: str
    enqueued: bool = False
    queue_error: str | None = None


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

    video_path = Path(settings.data_dir) / video.file_path
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="Video file not uploaded")

    if video.sha256 is None:
        raise HTTPException(
            status_code=400, detail="Video not finalized (sha256 missing)"
        )

    job = Job(
        video_id=video_id,
        status="PENDING",
        progress=0,
        config_json=body.config_overrides,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        get_queue().enqueue(
            process_video_job, str(job.id), job_timeout=DEFAULT_JOB_TIMEOUT_SEC
        )
        return JobCreateResponse(job_id=job.id, status=job.status, enqueued=True)
    except Exception as e:
        job.status = "FAILED"
        job.error = f"queue_error: {e}"
        job.finished_at = _utcnow()
        db.commit()
        return JobCreateResponse(
            job_id=job.id, status=job.status, enqueued=False, queue_error=str(e)
        )


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


@router.post("/jobs/{job_id}/cancel", response_model=JobActionResponse)
def cancel_job(job_id: UUID, db: Session = Depends(get_db)) -> JobActionResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in {"DONE", "FAILED"}:
        raise HTTPException(
            status_code=400, detail=f"Cannot cancel job in status {job.status}"
        )

    job.status = "CANCELED"
    job.finished_at = _utcnow()
    db.commit()
    db.refresh(job)

    return JobActionResponse(job_id=job.id, status=job.status)


@router.post("/jobs/{job_id}/retry", response_model=JobActionResponse)
def retry_job(job_id: UUID, db: Session = Depends(get_db)) -> JobActionResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in {"FAILED", "CANCELED"}:
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry FAILED/CANCELED jobs (got {job.status})",
        )

    job.status = "PENDING"
    job.progress = 0
    job.error = None
    job.started_at = None
    job.finished_at = None
    db.commit()
    db.refresh(job)

    try:
        get_queue().enqueue(
            process_video_job, str(job.id), job_timeout=DEFAULT_JOB_TIMEOUT_SEC
        )
        return JobActionResponse(job_id=job.id, status=job.status, enqueued=True)
    except Exception as e:
        job.status = "FAILED"
        job.error = f"queue_error: {e}"
        job.finished_at = _utcnow()
        db.commit()
        return JobActionResponse(
            job_id=job.id, status=job.status, enqueued=False, queue_error=str(e)
        )


@router.post("/jobs/{job_id}/recompute", response_model=JobRecomputeResponse)
def recompute_job(
    job_id: UUID, body: JobRecomputeRequest, db: Session = Depends(get_db)
) -> JobRecomputeResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == "RUNNING":
        raise HTTPException(status_code=400, detail="Job is RUNNING")

    assigned_tracks = _assign_identities_for_job(
        db, job_id=job_id, min_confidence=float(body.min_confidence)
    )

    if body.recompute_rollups:
        store_id, business_date = get_store_day_context(db, job_id=job_id)
        related = get_related_job_ids(
            db, store_id=store_id, business_date=business_date
        )
        all_job_ids = sorted(set(related + [job_id]))

        recompute_metrics_hourly_for_job(db, job_id=job_id)
        recompute_attendance_for_store_day(
            db,
            store_id=store_id,
            business_date=business_date,
            job_ids=all_job_ids,
        )

    if body.rewrite_artifacts:
        write_job_artifacts(db, job_id=job_id)

    return JobRecomputeResponse(
        job_id=job_id, assigned_tracks=int(assigned_tracks)
    )
