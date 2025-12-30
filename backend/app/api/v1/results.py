from datetime import date, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
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
)

router = APIRouter(tags=["results"])


class EventOut(BaseModel):
    id: UUID
    ts: datetime
    event_type: str
    entrance_id: str | None
    track_key: str
    employee_id: UUID | None
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
            confidence=e.confidence,
            is_inferred=e.is_inferred,
            meta=e.meta,
        )
        for e in rows
    ]


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
