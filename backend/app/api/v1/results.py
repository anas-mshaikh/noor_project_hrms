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

from app.auth.deps import require_permission
from app.auth.permissions import VISION_RESULTS_READ
from app.db.session import get_db
from app.models.models import (
    AttendanceDaily,
    Event,
    Job,
    MetricsHourly,
    Video,
)
from app.core.config import settings
from app.models.models import Artifact
from app.shared.types import AuthContext


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


def _require_branch_info(
    db: Session,
    *,
    tenant_id: UUID,
    branch_id: UUID,
) -> tuple[UUID, str]:
    row = db.execute(
        sa.text(
            """
            SELECT company_id, timezone
            FROM tenancy.branches
            WHERE id = :branch_id
              AND tenant_id = :tenant_id
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    company_id = row[0]
    tz = row[1] or "UTC"
    return company_id, tz


def _require_job_video_in_branch(
    db: Session,
    *,
    tenant_id: UUID,
    branch_id: UUID,
    job_id: UUID,
) -> tuple[Job, Video]:
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
        raise HTTPException(status_code=404, detail="Job not found")
    return row[0], row[1]


def _list_branch_employees(
    db: Session,
    *,
    tenant_id: UUID,
    company_id: UUID,
    branch_id: UUID,
    include_inactive: bool,
) -> list[tuple[UUID, str, str]]:
    # Canonical "current employment" selection (mirrors hr_core repo logic).
    where_status = "" if include_inactive else "AND e.status = 'ACTIVE'"
    rows = db.execute(
        sa.text(
            f"""
            WITH current_employment AS (
              SELECT
                ee.employee_id,
                ee.branch_id,
                ROW_NUMBER() OVER (
                  PARTITION BY ee.employee_id
                  ORDER BY ee.is_primary DESC NULLS LAST, ee.start_date DESC, ee.id DESC
                ) AS rn
              FROM hr_core.employee_employment ee
              WHERE ee.tenant_id = :tenant_id
                AND ee.company_id = :company_id
                AND ee.end_date IS NULL
            ),
            ce AS (
              SELECT employee_id, branch_id
              FROM current_employment
              WHERE rn = 1
            )
            SELECT
              e.id AS employee_id,
              e.employee_code AS employee_code,
              p.first_name AS first_name,
              p.last_name AS last_name
            FROM ce
            JOIN hr_core.employees e ON e.id = ce.employee_id
            JOIN hr_core.persons p ON p.id = e.person_id
            WHERE e.tenant_id = :tenant_id
              AND e.company_id = :company_id
              AND ce.branch_id = :branch_id
              {where_status}
            ORDER BY e.employee_code ASC, e.id ASC
            """
        ),
        {"tenant_id": tenant_id, "company_id": company_id, "branch_id": branch_id},
    ).all()

    out: list[tuple[UUID, str, str]] = []
    for r in rows:
        full_name = f"{r.first_name} {r.last_name}".strip()
        out.append((r.employee_id, r.employee_code, full_name))
    return out


@router.get("/branches/{branch_id}/jobs/{job_id}/events", response_model=list[EventOut])
def list_events(
    branch_id: UUID,
    job_id: UUID,
    event_type: str | None = Query(default=None),
    employee_id: UUID | None = Query(default=None),
    is_inferred: bool | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    ctx: AuthContext = Depends(require_permission(VISION_RESULTS_READ)),
    db: Session = Depends(get_db),
) -> list[EventOut]:
    _job, _video = _require_job_video_in_branch(
        db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, job_id=job_id
    )
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


@router.get("/branches/{branch_id}/events/{event_id}/snapshot")
def download_event_snapshot(
    branch_id: UUID,
    event_id: UUID,
    ctx: AuthContext = Depends(require_permission(VISION_RESULTS_READ)),
    db: Session = Depends(get_db),
) -> FileResponse:
    """
    Secure view/download endpoint for per-event snapshots (entry/exit frames).

    This is useful for the UI to show a thumbnail/preview while keeping disk paths opaque.
    """
    row = (
        db.query(Event)
        .join(Job, Job.id == Event.job_id)
        .join(Video, Video.id == Job.video_id)
        .filter(
            Event.id == event_id,
            Video.tenant_id == ctx.scope.tenant_id,
            Video.branch_id == branch_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")
    e = row

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


@router.get("/branches/{branch_id}/jobs/{job_id}/attendance", response_model=list[AttendanceOut])
def list_attendance(
    branch_id: UUID,
    job_id: UUID,
    ctx: AuthContext = Depends(require_permission(VISION_RESULTS_READ)),
    db: Session = Depends(get_db),
) -> list[AttendanceOut]:
    # Resolve branch/day via video so we return all employees for that branch/day.
    _job, video = _require_job_video_in_branch(
        db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, job_id=job_id
    )

    company_id, _tz = _require_branch_info(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id)

    business_date = video.business_date

    employees = _list_branch_employees(
        db,
        tenant_id=ctx.scope.tenant_id,
        company_id=company_id,
        branch_id=branch_id,
        include_inactive=False,
    )
    att_rows = (
        db.query(AttendanceDaily)
        .filter(
            AttendanceDaily.tenant_id == ctx.scope.tenant_id,
            AttendanceDaily.branch_id == branch_id,
            AttendanceDaily.business_date == business_date,
        )
        .all()
    )
    att_by_emp = {r.employee_id: r for r in att_rows}

    out: list[AttendanceOut] = []
    for emp_id, emp_code, emp_name in employees:
        att = att_by_emp.get(emp_id)
        if att is None:
            out.append(
                AttendanceOut(
                    employee_id=emp_id,
                    employee_code=emp_code,
                    employee_name=emp_name,
                    business_date=business_date,
                    punch_in=None,
                    punch_out=None,
                    total_minutes=0,
                    anomalies_json={"absent": True},
                )
            )
            continue

        out.append(
            AttendanceOut(
                employee_id=emp_id,
                employee_code=emp_code,
                employee_name=emp_name,
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
    "/branches/{branch_id}/attendance/daily",
    response_model=list[AttendanceDailySummaryOut],
)
def list_attendance_daily(
    branch_id: UUID,
    start: date = Query(...),
    end: date = Query(...),
    late_after: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    ctx: AuthContext = Depends(require_permission(VISION_RESULTS_READ)),
    db: Session = Depends(get_db),
) -> list[AttendanceDailySummaryOut]:
    company_id, tz_name = _require_branch_info(
        db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id
    )

    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")

    try:
        tz = ZoneInfo(tz_name or "UTC")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid branch timezone") from e

    late_after_minutes = _parse_hhmm_to_minutes(late_after)

    employees = _list_branch_employees(
        db,
        tenant_id=ctx.scope.tenant_id,
        company_id=company_id,
        branch_id=branch_id,
        include_inactive=bool(include_inactive),
    )
    total_employees = len(employees)
    allowed_employee_ids = {e[0] for e in employees}

    rows = (
        db.query(AttendanceDaily)
        .filter(
            AttendanceDaily.tenant_id == ctx.scope.tenant_id,
            AttendanceDaily.branch_id == branch_id,
            AttendanceDaily.business_date >= start,
            AttendanceDaily.business_date <= end,
        )
        .all()
    )
    if not include_inactive:
        rows = [r for r in rows if r.employee_id in allowed_employee_ids]

    # Attendance overrides (Leave + Corrections) affect "effective presence".
    #
    # Precedence:
    # 1) ON_LEAVE wins over everything (exclude from present)
    # 2) CORRECTION wins over base attendance
    # 3) Base attendance row -> present
    present_like_overrides = {"PRESENT_OVERRIDE", "WFH", "ON_DUTY"}

    att_by_key: dict[tuple[date, UUID], AttendanceDaily] = {
        (r.business_date, r.employee_id): r for r in rows
    }

    # Load overrides for the active branch/date range, filtered to the employee list.
    override_rows = db.execute(
        sa.text(
            """
            SELECT employee_id, day, status, override_kind, created_at, id
            FROM attendance.day_overrides
            WHERE tenant_id = :tenant_id
              AND branch_id = :branch_id
              AND day >= :start
              AND day <= :end
              AND employee_id = ANY(CAST(:employee_ids AS uuid[]))
            ORDER BY created_at DESC, id DESC
            """
        ),
        {
            "tenant_id": ctx.scope.tenant_id,
            "branch_id": branch_id,
            "start": start,
            "end": end,
            "employee_ids": list(allowed_employee_ids),
        },
    ).mappings().all()

    leave_keys: set[tuple[date, UUID]] = set()
    corr_status_by_key: dict[tuple[date, UUID], str] = {}
    for o in override_rows:
        k = (o["day"], UUID(str(o["employee_id"])))
        st = str(o["status"])
        if st == "ON_LEAVE":
            leave_keys.add(k)
            continue
        # Newest correction wins (ORDER BY created_at DESC).
        if k not in corr_status_by_key:
            corr_status_by_key[k] = st

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

    # Compute per-day stats using effective presence rules.
    for business_date in sorted(per_day.keys()):
        bucket = per_day[business_date]

        for emp_id in allowed_employee_ids:
            key = (business_date, emp_id)

            # Leave overrides win.
            if key in leave_keys:
                continue

            corr_status = corr_status_by_key.get(key)
            att = att_by_key.get(key)

            if corr_status is not None:
                # Correction overrides win over base.
                if corr_status in present_like_overrides:
                    bucket["present"] += 1
                else:
                    # ABSENT_OVERRIDE or unknown -> not present
                    continue
            else:
                # Base attendance row implies present.
                if att is None:
                    continue
                bucket["present"] += 1

            # Late/averages are computed from base row only (if present).
            if att is None:
                continue

            if att.total_minutes is not None:
                bucket["worked_sum"] += float(att.total_minutes)
                bucket["worked_count"] += 1

            if att.punch_in is not None:
                local = att.punch_in.astimezone(tz)
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


@router.get("/branches/{branch_id}/jobs/{job_id}/metrics/hourly", response_model=list[MetricsHourlyOut])
def list_metrics_hourly(
    branch_id: UUID,
    job_id: UUID,
    ctx: AuthContext = Depends(require_permission(VISION_RESULTS_READ)),
    db: Session = Depends(get_db),
) -> list[MetricsHourlyOut]:
    _job, _video = _require_job_video_in_branch(
        db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, job_id=job_id
    )
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


@router.get("/branches/{branch_id}/jobs/{job_id}/artifacts", response_model=list[ArtifactOut])
def list_artifacts(
    branch_id: UUID,
    job_id: UUID,
    ctx: AuthContext = Depends(require_permission(VISION_RESULTS_READ)),
    db: Session = Depends(get_db),
) -> list[ArtifactOut]:
    _job, _video = _require_job_video_in_branch(
        db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, job_id=job_id
    )
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


@router.get("/branches/{branch_id}/artifacts/{artifact_id}/download")
def download_artifact(
    branch_id: UUID,
    artifact_id: UUID,
    ctx: AuthContext = Depends(require_permission(VISION_RESULTS_READ)),
    db: Session = Depends(get_db),
) -> FileResponse:
    """
    Secure download:
    - artifact.path is stored as a relative path
    - we refuse any path that resolves outside settings.data_dir
    """
    a = (
        db.query(Artifact)
        .join(Job, Job.id == Artifact.job_id)
        .join(Video, Video.id == Job.video_id)
        .filter(
            Artifact.id == artifact_id,
            Video.tenant_id == ctx.scope.tenant_id,
            Video.branch_id == branch_id,
        )
        .first()
    )
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
