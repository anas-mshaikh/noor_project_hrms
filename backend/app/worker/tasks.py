"""
Worker always creates its own DB session (SessionLocal()).
It checks job.status == "CANCELED" repeatedly (best-effort cancellation).
It marks DB FAILED even if RQ marks the job failed, so your API remains the
source of truth.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.models import Camera, Employee, Job, Video
from app.worker.rollup import (
    get_related_job_ids,
    get_store_day_context,
    recompute_attendance_for_store_day,
    recompute_metrics_hourly_for_job,
)
from app.worker.pipeline_stub import process_tracks_stub
from app.worker.zones import ZoneConfig, validate_zone_config
from app.worker.artifacts import write_job_artifacts
from app.worker.identity import assign_identities_for_job


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _set_job(db: Session, job: Job, **fields) -> None:
    # Convenience helper so status/progress updates are always committed.
    for key, value in fields.items():
        setattr(job, key, value)
    db.add(job)
    db.commit()
    db.refresh(job)


def _fallback_demo_zone_cfg() -> ZoneConfig:
    """
    A "toy" calibration that matches the synthetic bbox coordinates below.

    - Door line is x = 0
    - x < 0 is OUTSIDE, x > 0 is INSIDE
    - Neutral band keeps x close to 0 as UNKNOWN so we don't flicker
    """
    return ZoneConfig(
        inside=[(0, 0), (200, 0), (200, 400), (0, 400)],
        outside=[(-200, 0), (0, 0), (0, 400), (-200, 400)],
        entry_line_p1=(0, 0),
        entry_line_p2=(0, 400),
        inside_test_point=(100, 200),
        neutral_band_px=10,
        # Optional: a small gate around the line (makes inferred events stricter)
        gate=[(-50, 0), (50, 0), (50, 400), (-50, 400)],
    )


def process_video_job(job_id: str) -> None:
    """
    RQ entrypoint.

    Current behavior:
    - Reads camera calibration_json (if present)
    - Runs pipeline_stub (synthetic frames) to generate tracks/events
    - Runs rollups (metrics + attendance)

    Later you’ll replace the stub section with: decode → detect/track → zone
    events → face match → rollups.
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

        # TODO: ---- PIPELINE STUB (replace later with real CV) ----
        # ----------------------------
        # Load calibration (camera)
        # ----------------------------
        camera = db.get(Camera, video.camera_id)
        if camera is None:
            raise RuntimeError("Camera not found for video")

        zone_cfg = ZoneConfig.from_calibration_json(
            camera.calibration_json or {},
            target_width=video.width,
            target_height=video.height,
        )

        errors, warnings = validate_zone_config(zone_cfg)
        if errors:
            raise RuntimeError(f"Invalid camera calibration: {errors}")
        # NOTE: Optional: later you can log warnings to DB/job logs

        # ----------------------------
        # Demo identity (so attendance rollup has employee_id)
        # ----------------------------
        # This is just to make Swagger testing nicer until face recognition is implemented.
        default_employee = (
            db.query(Employee)
            .filter(Employee.store_id == video.store_id, Employee.is_active.is_(True))
            .order_by(Employee.employee_code.asc())
            .first()
        )
        # default_employee_id = default_employee.id if default_employee else None

        # Make sure the synthetic movement actually crosses x=0:
        #   outside (x<0) -> neutral -> inside (x>0)
        def _video_start_ts(video: Video) -> datetime:
            # Prefer user-provided timestamp (best for business-day correctness)
            ts = video.recorded_start_ts
            if ts is None:
                # Fallback: business date midnight UTC (simple + deterministic)
                return datetime.combine(video.business_date, time(0, 0), tzinfo=timezone.utc)

            # Ensure tz-aware
            if ts.tzinfo is None:
                return ts.replace(tzinfo=timezone.utc)
            return ts

        t0 = _video_start_ts(video)
        frames = [
            (t0 + timedelta(seconds=0), [("track-1", (-120, 100, -100, 220))]),
            (t0 + timedelta(seconds=1), [("track-1", (-110, 105, -90, 225))]),
            (
                t0 + timedelta(seconds=2),
                [("track-1", (-10, 110, 10, 230))],
            ),  # neutral band
            (t0 + timedelta(seconds=3), [("track-1", (90, 120, 110, 240))]),
            (t0 + timedelta(seconds=4), [("track-1", (100, 125, 120, 245))]),
            (t0 + timedelta(seconds=5), [("track-1", (110, 130, 130, 250))]),
            # Track disappears here; pipeline_stub will infer EXIT ("track_ended_inside").
        ]

        process_tracks_stub(
            db,
            job_id=job_uuid,
            frames=frames,
            zone_cfg=zone_cfg,
            default_employee_id=None,
        )

        # Assign employee_id to tracks/events using pgvector (Phase 1 stub embeddings)
        assign_identities_for_job(db, job_id=job_uuid)

        job = db.get(Job, job_uuid)  # Refresh job
        if job is None:
            return
        if job.status == "CANCELED":
            _set_job(db, job, finished_at=_utcnow())
            return

        _set_job(db, job, status="POSTPROCESSING", progress=95)

        # Derive metrics and attendance for this store/day using all DONE jobs
        store_id, business_date = get_store_day_context(db, job_id=job_uuid)
        related_job_ids = get_related_job_ids(
            db, store_id=store_id, business_date=business_date
        )
        all_job_ids = sorted(set(related_job_ids + [job_uuid]))

        recompute_metrics_hourly_for_job(db, job_id=job_uuid)
        recompute_attendance_for_store_day(
            db,
            store_id=store_id,
            business_date=business_date,
            job_ids=all_job_ids,
        )

        # Write CSV/JSON exports to disk + insert rows in artifacts table
        write_job_artifacts(db, job_id=job_uuid)

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
