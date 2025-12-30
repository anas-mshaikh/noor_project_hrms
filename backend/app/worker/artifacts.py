"""
artifacts.py

After a job finishes, we want export files that a manager can download:

- events.csv      (auditable event log)
- attendance.csv  (daily punch-in/out rollup for that store/day)
- report.json     (small summary for debugging/analytics)

We also insert rows into the `artifacts` DB table so the API can list/download them.

Security note:
- We store artifact paths as *relative* paths under settings.data_dir.
- The download endpoint will enforce "path must stay inside data_dir".
"""

from __future__ import annotations
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Artifact, AttendanceDaily, Employee, Event, Job, Video


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _data_dir() -> Path:
    # Resolve so relative paths can't escape via ".."
    return Path(settings.data_dir).resolve()


def _abs_from_rel(rel_path: str) -> Path:
    """
    Convert a DB-stored relative path into an absolute filesystem path.

    Example:
      rel_path = "jobs/<job_id>/exports/events.csv"
      abs_path = "<data_dir>/jobs/<job_id>/exports/events.csv"
    """
    base = _data_dir()
    return (base / rel_path).resolve()


def _rel_from_abs(abs_path: Path) -> str:
    """
    Convert an absolute path back into a path relative to data_dir.
    This is what we store in `artifacts.path`.
    """
    base = _data_dir()
    return str(abs_path.resolve().relative_to(base))


def _exports_dir(job_id: UUID) -> Path:
    # /data/jobs/{job_id}/exports
    return _data_dir() / "jobs" / str(job_id) / "exports"


def write_job_artifacts(db: Session, *, job_id: UUID) -> list[Artifact]:
    """
    Create export files for a job and store them in the artifacts table.

    We delete prior artifacts for this job (so reruns don't create duplicates).
    """
    job = db.get(Job, job_id)
    if job is None:
        raise RuntimeError("Job not found")

    video = db.get(Video, job.video_id)
    if video is None:
        raise RuntimeError("Video not found for job")

    exports_dir = _exports_dir(job_id)
    exports_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------
    # 1) Export events.csv
    # -------------------------
    events_path = exports_dir / "events.csv"
    events = (
        db.query(Event).filter(Event.job_id == job_id).order_by(Event.ts.asc()).all()
    )

    with events_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "job_id",
                "ts",
                "event_type",
                "track_key",
                "employee_id",
                "is_inferred",
                "confidence",
                "reason",
                "meta_json",
            ],
        )
        writer.writeheader()

        for e in events:
            writer.writerow(
                {
                    "job_id": str(e.job_id),
                    "ts": e.ts.isoformat(),
                    "event_type": e.event_type,
                    "track_key": e.track_key,
                    "employee_id": str(e.employee_id) if e.employee_id else "",
                    "is_inferred": bool(e.is_inferred),
                    "confidence": "" if e.confidence is None else float(e.confidence),
                    "reason": (e.meta or {}).get("reason", ""),
                    "meta_json": json.dumps(e.meta or {}, separators=(",", ":")),
                }
            )

    # -------------------------
    # 2) Export attendance.csv
    # -------------------------
    attendance_path = exports_dir / "attendance.csv"

    # Left join attendance so absentees show up too (same as results endpoint).
    rows = (
        db.query(Employee, AttendanceDaily)
        .outerjoin(
            AttendanceDaily,
            sa.and_(
                AttendanceDaily.employee_id == Employee.id,
                AttendanceDaily.store_id == video.store_id,
                AttendanceDaily.business_date == video.business_date,
            ),
        )
        .filter(Employee.store_id == video.store_id)
        .order_by(Employee.employee_code.asc())
        .all()
    )

    with attendance_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "store_id",
                "business_date",
                "employee_id",
                "employee_code",
                "employee_name",
                "punch_in",
                "punch_out",
                "total_minutes",
                "anomalies_json",
            ],
        )
        writer.writeheader()

        for emp, att in rows:
            if att is None:
                anomalies = {"absent": True}
                punch_in = ""
                punch_out = ""
                total_minutes = 0
            else:
                anomalies = att.anomalies_json or {}
                punch_in = att.punch_in.isoformat() if att.punch_in else ""
                punch_out = att.punch_out.isoformat() if att.punch_out else ""
                total_minutes = (
                    "" if att.total_minutes is None else int(att.total_minutes)
                )

            writer.writerow(
                {
                    "store_id": str(video.store_id),
                    "business_date": video.business_date.isoformat(),
                    "employee_id": str(emp.id),
                    "employee_code": emp.employee_code,
                    "employee_name": emp.name,
                    "punch_in": punch_in,
                    "punch_out": punch_out,
                    "total_minutes": total_minutes,
                    "anomalies_json": json.dumps(anomalies, separators=(",", ":")),
                }
            )

    # -------------------------
    # 3) Export report.json
    # -------------------------
    report_path = exports_dir / "report.json"
    report = {
        "job_id": str(job.id),
        "video_id": str(video.id),
        "store_id": str(video.store_id),
        "camera_id": str(video.camera_id),
        "business_date": video.business_date.isoformat(),
        "generated_at": _utcnow_iso(),
        "counts": {
            "events": len(events),
            "entries": sum(1 for e in events if e.event_type == "entry"),
            "exits": sum(1 for e in events if e.event_type == "exit"),
            "inferred": sum(1 for e in events if e.is_inferred),
        },
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # -------------------------
    # 4) Store artifact rows
    # -------------------------
    db.query(Artifact).filter(Artifact.job_id == job_id).delete()
    db.commit()

    artifact_rows = [
        Artifact(job_id=job_id, type="csv", path=_rel_from_abs(events_path)),
        Artifact(job_id=job_id, type="csv", path=_rel_from_abs(attendance_path)),
        Artifact(job_id=job_id, type="json", path=_rel_from_abs(report_path)),
    ]
    db.add_all(artifact_rows)
    db.commit()

    return artifact_rows
