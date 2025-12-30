from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.models import (
    AttendanceDaily,
    Employee,
    Event,
    Job,
    MetricsHourly,
    Video,
)


def _hour_start(ts: datetime) -> datetime:
    # Normalize to hour boundary; ensure tz-aware
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.replace(minute=0, second=0, microsecond=0)


def _pair_sessions(
    events: list[Event],
) -> tuple[list[tuple[datetime, datetime]], dict[str, Any]]:
    """
    Greedy pairing of entry/exit in time order, using both observed and inferred events.
    Returns (sessions, anomalies_partial).
    """
    anomalies: dict[str, Any] = {}
    sessions: list[tuple[datetime, datetime]] = []
    open_in: datetime | None = None

    for e in sorted(events, key=lambda x: x.ts):
        if e.event_type == "entry":
            if open_in is None:
                open_in = e.ts
            else:
                anomalies["duplicate_entry"] = True
        else:  # exit
            if open_in is not None and e.ts > open_in:
                sessions.append((open_in, e.ts))
                open_in = None
            else:
                anomalies["exit_without_entry"] = True

    if open_in is not None:
        anomalies["missing_exit"] = True

    return sessions, anomalies


def recompute_attendance_for_store_day(
    db: Session,
    *,
    store_id: UUID,
    business_date: date,
    job_ids: list[UUID],
) -> None:
    """
    Recompute attendance_daily for ALL active employees in the store/day
    using events from the given job_ids (typically all DONE jobs for that day).
    """
    employees = (
        db.query(Employee)
        .filter(Employee.store_id == store_id, Employee.is_active.is_(True))
        .order_by(Employee.employee_code.asc())
        .all()
    )

    events = (
        db.query(Event)
        .filter(Event.job_id.in_(job_ids), Event.employee_id.isnot(None))
        .order_by(Event.ts.asc())
        .all()
    )

    events_by_employee: dict[UUID, list[Event]] = defaultdict(list)
    for e in events:
        events_by_employee[e.employee_id].append(e)  # type: ignore[arg-type]

    for emp in employees:
        emp_events = events_by_employee.get(emp.id, [])

        # Punch-in priority: observed entry -> inferred entry -> None
        observed_entries = [
            e.ts for e in emp_events if e.event_type == "entry" and not e.is_inferred
        ]
        inferred_entries = [
            e.ts for e in emp_events if e.event_type == "entry" and e.is_inferred
        ]
        punch_in = (
            min(observed_entries)
            if observed_entries
            else (min(inferred_entries) if inferred_entries else None)
        )

        # Punch-out priority: observed exit -> inferred exit -> None
        observed_exits = [
            e.ts for e in emp_events if e.event_type == "exit" and not e.is_inferred
        ]
        inferred_exits = [
            e.ts for e in emp_events if e.event_type == "exit" and e.is_inferred
        ]
        punch_out = (
            max(observed_exits)
            if observed_exits
            else (max(inferred_exits) if inferred_exits else None)
        )

        sessions, anomalies = _pair_sessions(emp_events)

        if punch_in is None and punch_out is None:
            anomalies = {"absent": True}
            total_minutes: int | None = 0
        else:
            if punch_in is None:
                anomalies["missing_entry"] = True
            if punch_out is None:
                anomalies["missing_exit"] = True

            if sessions:
                total_minutes = int(
                    sum((out - inn).total_seconds() for inn, out in sessions) // 60
                )
            elif punch_in and punch_out and punch_out > punch_in:
                total_minutes = int((punch_out - punch_in).total_seconds() // 60)
            else:
                total_minutes = None

        row = (
            db.query(AttendanceDaily)
            .filter(
                AttendanceDaily.store_id == store_id,
                AttendanceDaily.business_date == business_date,
                AttendanceDaily.employee_id == emp.id,
            )
            .one_or_none()
        )
        if row is None:
            row = AttendanceDaily(
                store_id=store_id, business_date=business_date, employee_id=emp.id
            )
            db.add(row)

        row.punch_in = punch_in
        row.punch_out = punch_out
        row.total_minutes = total_minutes
        row.anomalies_json = anomalies
        row.confidence = (
            None  # fill later once face-recognition confidence is aggregated
        )

    db.commit()


def recompute_metrics_hourly_for_job(db: Session, *, job_id: UUID) -> None:
    """
    Recompute metrics_hourly for one job (entries/exits/visitors/dwell).
    """
    db.query(MetricsHourly).filter(MetricsHourly.job_id == job_id).delete()
    db.commit()

    events = (
        db.query(Event).filter(Event.job_id == job_id).order_by(Event.ts.asc()).all()
    )

    by_hour: dict[datetime, dict[str, Any]] = defaultdict(
        lambda: {"entries": 0, "exits": 0, "visitor_tracks": set(), "dwells": []}
    )
    by_track: dict[str, dict[str, datetime]] = defaultdict(dict)

    for e in events:
        h = _hour_start(e.ts)
        if e.event_type == "entry":
            by_hour[h]["entries"] += 1
        else:
            by_hour[h]["exits"] += 1

        if e.employee_id is None:  # treat unknown/visitor tracks as unique by track_key
            by_hour[h]["visitor_tracks"].add(e.track_key)

        if e.event_type == "entry" and "entry" not in by_track[e.track_key]:
            by_track[e.track_key]["entry"] = e.ts
        if e.event_type == "exit":
            by_track[e.track_key]["exit"] = e.ts

    # Dwell = exit - entry per track when both exist
    for track_key, t in by_track.items():
        if "entry" in t and "exit" in t and t["exit"] > t["entry"]:
            dwell = (t["exit"] - t["entry"]).total_seconds()
            h = _hour_start(t["entry"])
            by_hour[h]["dwells"].append(dwell)

    rows: list[MetricsHourly] = []
    for hour_start, agg in sorted(by_hour.items(), key=lambda x: x[0]):
        dwells = agg["dwells"]
        avg_dwell = (sum(dwells) / len(dwells)) if dwells else None

        rows.append(
            MetricsHourly(
                job_id=job_id,
                hour_start_ts=hour_start,
                entries=agg["entries"],
                exits=agg["exits"],
                unique_visitors=len(agg["visitor_tracks"]),
                avg_dwell_sec=avg_dwell,
            )
        )

    if rows:
        db.add_all(rows)
        db.commit()


def get_store_day_context(db: Session, *, job_id: UUID) -> tuple[UUID, date]:
    # Resolve job -> video to get store_id + business_date
    job = db.get(Job, job_id)
    if job is None:
        raise RuntimeError("Job not found")
    video = db.get(Video, job.video_id)
    if video is None:
        raise RuntimeError("Video not found")
    return video.store_id, video.business_date


def get_related_job_ids(
    db: Session, *, store_id: UUID, business_date: date
) -> list[UUID]:
    """
    Collect DONE jobs for this store/day (keeps daily attendance consistent if
    multiple videos processed).
    """
    ids = (
        db.query(Job.id)
        .join(Video, Job.video_id == Video.id)
        .filter(
            Video.store_id == store_id,
            Video.business_date == business_date,
            Job.status == "DONE",
        )
        .all()
    )
    return [row[0] for row in ids]
