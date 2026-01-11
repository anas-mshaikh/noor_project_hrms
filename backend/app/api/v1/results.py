from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any
from uuid import UUID

from pathlib import Path
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import (
    AttendanceDaily,
    Employee,
    Event,
    Job,
    MetricsHourly,
    Video,
    Store,
)
from app.core.config import settings
from app.models.models import Artifact


router = APIRouter(tags=["results"])


class ArtifactOut(BaseModel):
    id: UUID
    type: str
    path: str
    created_at: datetime


class EventOut(BaseModel):
    id: UUID
    ts: datetime
    event_type: str
    entrance_id: str | None
    track_key: str
    employee_id: UUID | None
    snapshot_path: str | None
    confidence: float | None
    is_inferred: bool
    meta: dict[str, Any]


class AttendanceOut(BaseModel):
    employee_id: UUID
    employee_code: str
    employee_name: str
    business_date: date
    punch_in: datetime | None
    punch_out: datetime | None
    total_minutes: int | None
    anomalies_json: dict[str, Any]


class MetricsHourlyOut(BaseModel):
    hour_start_ts: datetime
    entries: int
    exits: int
    unique_visitors: int
    avg_dwell_sec: float | None


class AttendanceDailySummaryOut(BaseModel):
    business_date: date
    total_employees: int
    present_count: int
    absent_count: int
    late_count: int
    avg_worked_minutes: float | None
    avg_punch_in_minutes: float | None


@router.get("/jobs/{job_id}/events", response_model=list[EventOut])
def list_events(
    job_id: UUID,
    event_type: str | None = Query(default=None),
    employee_id: UUID | None = Query(default=None),
    is_inferred: bool | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[EventOut]:
    # Filter by job and optional event_type/employee/inferred flag; paginated
    q = db.query(Event).filter(Event.job_id == job_id)

    if event_type is not None:
        if event_type not in {"entry", "exit"}:
            raise HTTPException(status_code=400, detail="event_type must be entry|exit")
        q = q.filter(Event.event_type == event_type)

    if employee_id is not None:
        q = q.filter(Event.employee_id == employee_id)

    if is_inferred is not None:
        q = q.filter(Event.is_inferred.is_(is_inferred))

    rows = q.order_by(Event.ts.asc()).offset(offset).limit(limit).all()

    return [
        EventOut(
            id=e.id,
            ts=e.ts,
            event_type=e.event_type,
            entrance_id=e.entrance_id,
            track_key=e.track_key,
            employee_id=e.employee_id,
            snapshot_path=e.snapshot_path,
            confidence=e.confidence,
            is_inferred=e.is_inferred,
            meta=e.meta,
        )
        for e in rows
    ]


@router.get("/events/{event_id}/snapshot")
def download_event_snapshot(
    event_id: UUID,
    db: Session = Depends(get_db),
) -> FileResponse:
    """
    Secure view/download endpoint for per-event snapshots (entry/exit frames).

    This is useful for the UI to show a thumbnail/preview while keeping disk paths opaque.
    """
    e = db.get(Event, event_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if e.snapshot_path is None or e.snapshot_path == "":
        raise HTTPException(status_code=404, detail="Event snapshot not available")

    base = Path(settings.data_dir).resolve()
    target = (base / e.snapshot_path).resolve()

    # Prevent path traversal (“../../etc/passwd”)
    if not target.is_relative_to(base):
        raise HTTPException(status_code=400, detail="Invalid snapshot path")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Snapshot file missing on disk")

    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(target.suffix.lower(), "application/octet-stream")

    # IMPORTANT: `inline` lets the browser open the image in a new tab
    # (instead of forcing a download via `attachment`).
    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type=media_type,
        content_disposition_type="inline",
    )


@router.get("/jobs/{job_id}/attendance", response_model=list[AttendanceOut])
def list_attendance(job_id: UUID, db: Session = Depends(get_db)) -> list[AttendanceOut]:
    # Resolve store/day via video so we return all employees for that store/day
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    video = db.get(Video, job.video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    store_id = video.store_id
    business_date = video.business_date

    # Left join attendance so absentees still show up with anomalies={"absent": true}
    rows = (
        db.query(Employee, AttendanceDaily)
        .outerjoin(
            AttendanceDaily,
            sa.and_(
                AttendanceDaily.employee_id == Employee.id,
                AttendanceDaily.store_id == store_id,
                AttendanceDaily.business_date == business_date,
            ),
        )
        .filter(Employee.store_id == store_id)
        .order_by(Employee.employee_code.asc())
        .all()
    )

    out: list[AttendanceOut] = []
    for emp, att in rows:
        if att is None:
            out.append(
                AttendanceOut(
                    employee_id=emp.id,
                    employee_code=emp.employee_code,
                    employee_name=emp.name,
                    business_date=business_date,
                    punch_in=None,
                    punch_out=None,
                    total_minutes=0,
                    anomalies_json={"absent": True},
                )
            )
        else:
            out.append(
                AttendanceOut(
                    employee_id=emp.id,
                    employee_code=emp.employee_code,
                    employee_name=emp.name,
                    business_date=att.business_date,
                    punch_in=att.punch_in,
                    punch_out=att.punch_out,
                    total_minutes=att.total_minutes,
                    anomalies_json=att.anomalies_json,
                )
            )

    return out


def _parse_hhmm_to_minutes(value: str | None) -> int | None:
    """
    Convert "HH:MM" -> minutes since midnight.
    Returns None if empty; raises 400 if malformed.
    """
    if value is None or value == "":
        return None

    parts = value.split(":")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="late_after must be HH:MM")

    try:
        h = int(parts[0])
        m = int(parts[1])
    except ValueError as e:
        raise HTTPException(status_code=400, detail="late_after must be HH:MM") from e

    if h < 0 or h > 23 or m < 0 or m > 59:
        raise HTTPException(status_code=400, detail="late_after must be HH:MM")

    return h * 60 + m


@router.get(
    "/stores/{store_id}/attendance/daily",
    response_model=list[AttendanceDailySummaryOut],
)
def list_attendance_daily(
    store_id: UUID,
    start: date = Query(...),
    end: date = Query(...),
    late_after: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[AttendanceDailySummaryOut]:
    # Store timezone drives "late" classification.
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")

    try:
        tz = ZoneInfo(store.timezone or "UTC")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid store timezone") from e

    late_after_minutes = _parse_hhmm_to_minutes(late_after)

    emp_q = db.query(Employee).filter(Employee.store_id == store_id)
    if not include_inactive:
        emp_q = emp_q.filter(Employee.is_active.is_(True))
    total_employees = int(emp_q.count())

    att_q = (
        db.query(AttendanceDaily)
        .join(Employee, AttendanceDaily.employee_id == Employee.id)
        .filter(
            Employee.store_id == store_id,
            AttendanceDaily.business_date >= start,
            AttendanceDaily.business_date <= end,
        )
    )
    if not include_inactive:
        att_q = att_q.filter(Employee.is_active.is_(True))
    rows = att_q.all()

    # Pre-fill all dates so missing days still return zeros.
    per_day: dict[date, dict[str, float]] = {}
    d = start
    while d <= end:
        per_day[d] = {
            "present": 0,
            "late": 0,
            "worked_sum": 0.0,
            "worked_count": 0,
            "punch_in_sum": 0.0,
            "punch_in_count": 0,
        }
        d += timedelta(days=1)

    for r in rows:
        bucket = per_day.get(r.business_date)
        if bucket is None:
            continue

        bucket["present"] += 1

        if r.total_minutes is not None:
            bucket["worked_sum"] += float(r.total_minutes)
            bucket["worked_count"] += 1

        if r.punch_in is not None:
            local = r.punch_in.astimezone(tz)
            minutes = local.hour * 60 + local.minute
            bucket["punch_in_sum"] += float(minutes)
            bucket["punch_in_count"] += 1

            if late_after_minutes is not None and minutes > late_after_minutes:
                bucket["late"] += 1

    out: list[AttendanceDailySummaryOut] = []
    for business_date in sorted(per_day.keys()):
        b = per_day[business_date]
        present = int(b["present"])
        absent = max(0, total_employees - present)

        avg_worked = (
            b["worked_sum"] / b["worked_count"] if b["worked_count"] > 0 else None
        )
        avg_punch_in = (
            b["punch_in_sum"] / b["punch_in_count"] if b["punch_in_count"] > 0 else None
        )

        out.append(
            AttendanceDailySummaryOut(
                business_date=business_date,
                total_employees=total_employees,
                present_count=present,
                absent_count=absent,
                late_count=int(b["late"]),
                avg_worked_minutes=avg_worked,
                avg_punch_in_minutes=avg_punch_in,
            )
        )

    return out


@router.get("/jobs/{job_id}/metrics/hourly", response_model=list[MetricsHourlyOut])
def list_metrics_hourly(
    job_id: UUID, db: Session = Depends(get_db)
) -> list[MetricsHourlyOut]:
    # Simple listing of hourly aggregates for the job
    rows = (
        db.query(MetricsHourly)
        .filter(MetricsHourly.job_id == job_id)
        .order_by(MetricsHourly.hour_start_ts.asc())
        .all()
    )

    return [
        MetricsHourlyOut(
            hour_start_ts=m.hour_start_ts,
            entries=m.entries,
            exits=m.exits,
            unique_visitors=m.unique_visitors,
            avg_dwell_sec=m.avg_dwell_sec,
        )
        for m in rows
    ]


@router.get("/jobs/{job_id}/artifacts", response_model=list[ArtifactOut])
def list_artifacts(job_id: UUID, db: Session = Depends(get_db)) -> list[ArtifactOut]:
    rows = (
        db.query(Artifact)
        .filter(Artifact.job_id == job_id)
        .order_by(Artifact.created_at.asc())
        .all()
    )
    return [
        ArtifactOut(id=a.id, type=a.type, path=a.path, created_at=a.created_at)
        for a in rows
    ]


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    """
    Secure download:
    - artifact.path is stored as a relative path
    - we refuse any path that resolves outside settings.data_dir
    """
    a = db.get(Artifact, artifact_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    base = Path(settings.data_dir).resolve()
    target = (base / a.path).resolve()

    # Prevent path traversal (“../../etc/passwd”)
    if not target.is_relative_to(base):
        raise HTTPException(status_code=400, detail="Invalid artifact path")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact file missing on disk")

    media_type = {
        "csv": "text/csv",
        "json": "application/json",
        "pdf": "application/pdf",
    }.get(a.type, "application/octet-stream")

    return FileResponse(path=str(target), filename=target.name, media_type=media_type)
