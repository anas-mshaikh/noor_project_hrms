"""
POST /videos/{video_id}/jobs creates + enqueues a processing run.
GET /jobs/{job_id} is the UI polling endpoint.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import require_permission
from app.auth.permissions import VISION_JOB_RUN, VISION_RESULTS_READ
from app.core.config import settings
from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.face_system.runtime_processor import get_runtime_processor
from app.models.models import Event, Job, Track, Video
from app.queue.rq import DEFAULT_JOB_TIMEOUT_SEC, get_queue
from app.worker.tasks import process_video_job
from app.worker.rollup import (
    get_related_job_ids,
    get_branch_day_context,
    recompute_attendance_for_branch_day,
    recompute_metrics_hourly_for_job,
)
from app.worker.artifacts import write_job_artifacts
from app.shared.types import AuthContext


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
    db: Session,
    *,
    tenant_id: UUID,
    branch_id: UUID,
    job_id: UUID,
    min_confidence: float,
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
        raise AppError(
            code="vision.dependencies.missing",
            message="opencv-python is required to decode snapshots for recompute",
            status_code=500,
        ) from e

    row = (
        db.query(Job, Video)
        .join(Video, Video.id == Job.video_id)
        .filter(
            Job.id == job_id,
            Video.tenant_id == tenant_id,
            Video.branch_id == branch_id,
        )
        .first()
    )
    if row is None:
        raise AppError(code="vision.job.not_found", message="Job not found", status_code=404)
    job, video = row

    # Load store prototypes (blocking build once).
    try:
        proc = get_runtime_processor(tenant_id=tenant_id, branch_id=branch_id, camera_id=None)
        proc.recognizer.ensure_built(block=True, timeout_sec=60.0)
    except Exception as e:
        raise AppError(
            code="vision.face_system.unavailable",
            message="Face system unavailable",
            status_code=500,
        ) from e

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
    "/branches/{branch_id}/videos/{video_id}/jobs",
    status_code=status.HTTP_201_CREATED,
)
def create_job(
    branch_id: UUID,
    video_id: UUID,
    body: JobCreateRequest,
    ctx: AuthContext = Depends(require_permission(VISION_JOB_RUN)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    video = (
        db.query(Video)
        .filter(
            Video.id == video_id,
            Video.tenant_id == ctx.scope.tenant_id,
            Video.branch_id == branch_id,
        )
        .first()
    )
    if video is None:
        raise AppError(code="vision.video.not_found", message="Video not found", status_code=404)

    video_path = Path(settings.data_dir) / video.file_path
    if not video_path.exists():
        raise AppError(
            code="vision.video.file_not_uploaded",
            message="Video file not uploaded",
            status_code=400,
        )

    if video.sha256 is None:
        raise AppError(
            code="vision.video.not_finalized",
            message="Video not finalized",
            status_code=400,
        )

    job = Job(
        tenant_id=ctx.scope.tenant_id,
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
        return ok(JobCreateResponse(job_id=job.id, status=job.status, enqueued=True).model_dump())
    except Exception as e:
        job.status = "FAILED"
        job.error = f"queue_error: {e}"
        job.finished_at = _utcnow()
        db.commit()
        return ok(
            JobCreateResponse(
                job_id=job.id, status=job.status, enqueued=False, queue_error=str(e)
            ).model_dump()
        )


@router.get("/branches/{branch_id}/jobs/{job_id}")
def get_job(
    branch_id: UUID,
    job_id: UUID,
    ctx: AuthContext = Depends(require_permission(VISION_RESULTS_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    job_row = (
        db.query(Job)
        .join(Video, Video.id == Job.video_id)
        .filter(
            Job.id == job_id,
            Video.tenant_id == ctx.scope.tenant_id,
            Video.branch_id == branch_id,
        )
        .first()
    )
    if job_row is None:
        raise AppError(code="vision.job.not_found", message="Job not found", status_code=404)
    job = job_row

    return ok(
        JobReadResponse(
            id=job.id,
            video_id=job.video_id,
            status=job.status,
            progress=job.progress,
            error=job.error,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        ).model_dump()
    )


@router.post("/branches/{branch_id}/jobs/{job_id}/cancel")
def cancel_job(
    branch_id: UUID,
    job_id: UUID,
    ctx: AuthContext = Depends(require_permission(VISION_JOB_RUN)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    job = (
        db.query(Job)
        .join(Video, Video.id == Job.video_id)
        .filter(
            Job.id == job_id,
            Video.tenant_id == ctx.scope.tenant_id,
            Video.branch_id == branch_id,
        )
        .first()
    )
    if job is None:
        raise AppError(code="vision.job.not_found", message="Job not found", status_code=404)

    if job.status in {"DONE", "FAILED"}:
        raise AppError(
            code="vision.job.invalid_state",
            message=f"Cannot cancel job in status {job.status}",
            status_code=400,
        )

    job.status = "CANCELED"
    job.finished_at = _utcnow()
    db.commit()
    db.refresh(job)

    return ok(JobActionResponse(job_id=job.id, status=job.status).model_dump())


@router.post("/branches/{branch_id}/jobs/{job_id}/retry")
def retry_job(
    branch_id: UUID,
    job_id: UUID,
    ctx: AuthContext = Depends(require_permission(VISION_JOB_RUN)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    job = (
        db.query(Job)
        .join(Video, Video.id == Job.video_id)
        .filter(
            Job.id == job_id,
            Video.tenant_id == ctx.scope.tenant_id,
            Video.branch_id == branch_id,
        )
        .first()
    )
    if job is None:
        raise AppError(code="vision.job.not_found", message="Job not found", status_code=404)

    if job.status not in {"FAILED", "CANCELED"}:
        raise AppError(
            code="vision.job.invalid_state",
            message=f"Can only retry FAILED/CANCELED jobs (got {job.status})",
            status_code=400,
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
        return ok(
            JobActionResponse(job_id=job.id, status=job.status, enqueued=True).model_dump()
        )
    except Exception as e:
        job.status = "FAILED"
        job.error = f"queue_error: {e}"
        job.finished_at = _utcnow()
        db.commit()
        return ok(
            JobActionResponse(
                job_id=job.id, status=job.status, enqueued=False, queue_error=str(e)
            ).model_dump()
        )


@router.post("/branches/{branch_id}/jobs/{job_id}/recompute")
def recompute_job(
    branch_id: UUID,
    job_id: UUID,
    body: JobRecomputeRequest,
    ctx: AuthContext = Depends(require_permission(VISION_JOB_RUN)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    job = (
        db.query(Job)
        .join(Video, Video.id == Job.video_id)
        .filter(
            Job.id == job_id,
            Video.tenant_id == ctx.scope.tenant_id,
            Video.branch_id == branch_id,
        )
        .first()
    )
    if job is None:
        raise AppError(code="vision.job.not_found", message="Job not found", status_code=404)

    if job.status == "RUNNING":
        raise AppError(code="vision.job.invalid_state", message="Job is RUNNING", status_code=400)

    assigned_tracks = _assign_identities_for_job(
        db,
        tenant_id=ctx.scope.tenant_id,
        branch_id=branch_id,
        job_id=job_id,
        min_confidence=float(body.min_confidence),
    )

    if body.recompute_rollups:
        tenant_id2, branch_id2, business_date = get_branch_day_context(db, job_id=job_id)
        if tenant_id2 != ctx.scope.tenant_id or branch_id2 != branch_id:
            raise AppError(code="vision.job.not_found", message="Job not found", status_code=404)
        related = get_related_job_ids(
            db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, business_date=business_date
        )
        all_job_ids = sorted(set(related + [job_id]))

        recompute_metrics_hourly_for_job(db, job_id=job_id)
        recompute_attendance_for_branch_day(
            db,
            tenant_id=ctx.scope.tenant_id,
            branch_id=branch_id,
            business_date=business_date,
            job_ids=all_job_ids,
        )

    if body.rewrite_artifacts:
        write_job_artifacts(db, job_id=job_id)

    return ok(
        JobRecomputeResponse(job_id=job_id, assigned_tracks=int(assigned_tracks)).model_dump()
    )
