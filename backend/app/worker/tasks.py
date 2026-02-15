"""
Worker always creates its own DB session (SessionLocal()).
It checks job.status == "CANCELED" repeatedly (best-effort cancellation).
It marks DB FAILED even if RQ marks the job failed, so your API remains the
source of truth.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.models import (
    Artifact,
    Camera,
    Event,
    Job,
    MetricsHourly,
    Track,
    Video,
)
from app.worker.artifacts import write_job_artifacts
from app.worker.rollup import (
    get_related_job_ids,
    get_branch_day_context,
    recompute_attendance_for_branch_day,
    recompute_metrics_hourly_for_job,
)
from app.worker.zones import ZoneConfig, validate_zone_config


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _set_job(db: Session, job: Job, **fields) -> None:
    # Convenience helper so status/progress updates are always committed.
    for key, value in fields.items():
        setattr(job, key, value)
    db.add(job)
    db.commit()
    db.refresh(job)


def _clear_job_outputs(db: Session, *, job_id: UUID) -> None:
    """
    Ensure retries are idempotent: delete old outputs for this job.
    """
    db.query(Event).filter(Event.job_id == job_id).delete()
    db.query(Track).filter(Track.job_id == job_id).delete()
    db.query(MetricsHourly).filter(MetricsHourly.job_id == job_id).delete()
    db.query(Artifact).filter(Artifact.job_id == job_id).delete()
    db.commit()


def process_video_job(job_id: str) -> None:
    """
    RQ entrypoint.

    Pipeline:
    - Load job + video + camera + store timezone
    - Parse & validate calibration
    - Run real CV pipeline (motion gate -> YOLO tracking -> events -> face ID)
    - Postprocess rollups + artifacts
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
        _clear_job_outputs(db, job_id=job_uuid)

        video = db.get(Video, job.video_id)
        if video is None:
            raise RuntimeError("Video not found for job")

        branch_tz_row = db.execute(
            sa.text(
                """
                SELECT timezone
                FROM tenancy.branches
                WHERE id = :branch_id
                  AND tenant_id = :tenant_id
                """
            ),
            {"tenant_id": video.tenant_id, "branch_id": video.branch_id},
        ).first()
        if branch_tz_row is None:
            raise RuntimeError("Branch not found for video")
        branch_timezone = str(branch_tz_row[0] or "UTC")

        camera = db.get(Camera, video.camera_id)
        if camera is None:
            raise RuntimeError("Camera not found for video")

        video_path = Path(settings.data_dir) / video.file_path
        if not video_path.exists():
            raise RuntimeError(f"Video file missing: {video.file_path}")

        # Ensure width/height/fps exist (needed for coord_space=normalized scaling).
        if video.width is None or video.height is None or video.fps is None:
            try:
                import cv2  # type: ignore
            except Exception as e:
                raise RuntimeError(
                    "opencv-python required to read video metadata"
                ) from e

            cap = cv2.VideoCapture(str(video_path))
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                cap.release()

                if video.width is None and w > 0:
                    video.width = w
                if video.height is None and h > 0:
                    video.height = h
                if video.fps is None and fps > 0:
                    video.fps = fps

                db.add(video)
                db.commit()

        # Parse and validate calibration
        zone_cfg = ZoneConfig.from_calibration_json(
            camera.calibration_json or {},
            target_width=video.width,
            target_height=video.height,
        )

        errors, warnings = validate_zone_config(zone_cfg)
        if errors:
            raise RuntimeError(f"Invalid camera calibration: {errors}")
        # warnings are safe to ignore for MVP; later you can store them in job logs

        # Lazy import heavy pipeline code (keeps API startup fast)
        from app.worker.pipeline import PipelineConfig, process_video_pipeline

        pipeline_cfg = PipelineConfig.from_job_config(job.config_json)

        # Progress callback (pipeline emits 0..90)
        last_progress = -1

        def on_progress(p: int) -> None:
            nonlocal last_progress
            p = max(0, min(int(p), 90))
            if p == last_progress:
                return
            last_progress = p
            _set_job(db, job, progress=p)

        # Cancellation check (best-effort, throttled)
        last_cancel_check = _utcnow()

        def should_cancel() -> bool:
            nonlocal last_cancel_check
            now = _utcnow()
            if (now - last_cancel_check).total_seconds() < 2.0:
                return False
            last_cancel_check = now
            db.refresh(job)
            return job.status == "CANCELED"

        pipeline_report = process_video_pipeline(
            db,
            job_id=job_uuid,
            video=video,
            zone_cfg=zone_cfg,
            store_timezone=branch_timezone,
            cfg=pipeline_cfg,
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

        db.refresh(job)
        if job.status == "CANCELED":
            _set_job(db, job, finished_at=_utcnow())
            return

        _set_job(db, job, status="POSTPROCESSING", progress=95)

        # Derive metrics and attendance for this branch/day using all DONE jobs
        tenant_id, branch_id, business_date = get_branch_day_context(db, job_id=job_uuid)
        related_job_ids = get_related_job_ids(
            db, tenant_id=tenant_id, branch_id=branch_id, business_date=business_date
        )
        all_job_ids = sorted(set(related_job_ids + [job_uuid]))

        recompute_metrics_hourly_for_job(db, job_id=job_uuid)
        recompute_attendance_for_branch_day(
            db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            business_date=business_date,
            job_ids=all_job_ids,
        )

        # Write CSV/JSON exports to disk + insert rows in artifacts table
        write_job_artifacts(db, job_id=job_uuid, pipeline_report=pipeline_report)

        db.refresh(job)
        if job.status == "CANCELED":
            _set_job(db, job, finished_at=_utcnow())
            return

        _set_job(db, job, status="DONE", progress=100, finished_at=_utcnow())

    except Exception as e:
        db.rollback()  # IMPORTANT: recover session after IntegrityError/etc.
        job = db.get(Job, job_uuid)
        if job is not None:
            _set_job(db, job, status="FAILED", error=str(e), finished_at=_utcnow())
        raise
    finally:
        db.close()
