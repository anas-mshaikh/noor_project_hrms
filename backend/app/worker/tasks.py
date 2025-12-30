"""
Worker always creates its own DB session (SessionLocal()).
It checks job.status == "CANCELED" repeatedly (best-effort cancellation).
It marks DB FAILED even if RQ marks the job failed, so your API remains the source of truth.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.models import Job, Video


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _set_job(db: Session, job: Job, **fields) -> None:
    for key, value in fields.items():
        setattr(job, key, value)
    db.add(job)
    db.commit()
    db.refresh(job)


def process_video_job(job_id: str) -> None:
    """
    RQ entrypoint.

    Current behavior: pipeline stub that only updates status/progress.
    Later you’ll replace the stub section with: decode → detect/track → zone events → face match → rollups.
    """
    job_uuid = uuid.UUID(job_id)
    db = SessionLocal()

    try:
        job = db.get(Job, job_uuid)
        if job is None:
            return

        # Idempotency / safety
        if job.status in {"RUNNING", "DONE"}:
            return
        if job.status == "CANCELED":
            return

        _set_job(
            db,
            job,
            status="RUNNING",
            progress=1,
            error=None,
            started_at=_utcnow(),
            finished_at=None,
        )

        video = db.get(Video, job.video_id)
        if video is None:
            raise RuntimeError("Video not found for job")

        video_path = Path(settings.data_dir) / video.file_path
        if not video_path.exists():
            raise RuntimeError(f"Video file missing: {video.file_path}")

        # ---- PIPELINE STUB (replace later) ----
        for pct in (10, 30, 60, 85):
            job = db.get(Job, job_uuid)
            if job is None:
                return
            if job.status == "CANCELED":
                _set_job(db, job, finished_at=_utcnow())
                return
            _set_job(db, job, progress=pct)
        # --------------------------------------

        job = db.get(Job, job_uuid)
        if job is None:
            return
        if job.status == "CANCELED":
            _set_job(db, job, finished_at=_utcnow())
            return

        _set_job(db, job, status="POSTPROCESSING", progress=95)

        # TODO: write artifacts/events/tracks + derive attendance/metrics

        job = db.get(Job, job_uuid)
        if job is None:
            return
        if job.status == "CANCELED":
            _set_job(db, job, finished_at=_utcnow())
            return

        _set_job(db, job, status="DONE", progress=100, finished_at=_utcnow())

    except Exception as e:
        job = db.get(Job, job_uuid)
        if job is not None:
            _set_job(db, job, status="FAILED", error=str(e), finished_at=_utcnow())
        raise
    finally:
        db.close()