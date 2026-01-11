from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import (
    AttendanceDaily,
    Employee,
    Event,
    Job,
    MetricsHourly,
    Track,
    Video,
)
from app.worker.reliability import Tracklet, group_stitched_tracklets, iter_session_groups


def _hour_start(ts: datetime) -> datetime:
    # Normalize to hour boundary; ensure tz-aware
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.replace(minute=0, second=0, microsecond=0)


def _pair_sessions(
    events: list[Event],
) -> tuple[list[tuple[datetime, datetime]], dict[str, Any]]:
    """
    Greedy pairing of entry/exit in time order, using both observed and
    inferred events.
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

    # Tracklets are used only for conservative "recognized-only stitching".
    # We stitch only when BOTH tracklets locked the same employee_id with high confidence.
    tracklets_by_employee: dict[UUID, list[Tracklet]] = defaultdict(list)
    if bool(settings.enable_recognized_stitching) and job_ids:
        tracks = (
            db.query(Track)
            .filter(
                Track.job_id.in_(job_ids),
                Track.employee_id.isnot(None),
                Track.identity_confidence.isnot(None),
            )
            .order_by(Track.first_ts.asc())
            .all()
        )
        for t in tracks:
            if t.employee_id is None or t.identity_confidence is None:
                continue
            tracklets_by_employee[t.employee_id].append(
                Tracklet(
                    track_key=t.track_key,
                    employee_id=t.employee_id,
                    lock_confidence=float(t.identity_confidence),
                    start_ts=t.first_ts,
                    end_ts=t.last_ts,
                    first_zone=t.first_seen_zone,
                    last_zone=t.last_seen_zone,
                )
            )

    for emp in employees:
        emp_events = events_by_employee.get(emp.id, [])

        # Apply extremely conservative recognized-only stitching.
        # This is "attendance-first": avoid false merges.
        stitched_groups: list[set[str]] = []
        if bool(settings.enable_recognized_stitching):
            tls = sorted(tracklets_by_employee.get(emp.id, []), key=lambda x: x.start_ts)
            if tls:
                mapping = group_stitched_tracklets(
                    tracklets=tls,
                    gap_sec=float(settings.stitch_gap_sec),
                    min_lock_score=float(settings.stitch_min_lock_score),
                    require_unique_candidate=bool(settings.stitch_require_unique_candidate),
                    require_inside_continuity=True,
                )
                stitched_groups = [g for g in iter_session_groups(mapping) if len(g) > 1]

        # For pairing sessions, suppress only the inferred "boundary" events created by track breaks.
        # We never remove observed (non-inferred) events like line_crossing.
        events_for_pairing = emp_events
        if stitched_groups:
            tracklet_by_key = {t.track_key: t for t in tracklets_by_employee.get(emp.id, [])}
            ignore_entry_for: set[str] = set()
            ignore_exit_for: set[str] = set()

            for g in stitched_groups:
                ordered = sorted(
                    (tracklet_by_key[k] for k in g if k in tracklet_by_key),
                    key=lambda t: t.start_ts,
                )
                if len(ordered) < 2:
                    continue
                first_key = ordered[0].track_key
                last_key = ordered[-1].track_key
                ignore_entry_for.update({t.track_key for t in ordered[1:]})
                ignore_exit_for.update({t.track_key for t in ordered[:-1]})

            def _is_boundary_event(e: Event) -> bool:
                reason = (e.meta or {}).get("reason", "")
                if e.track_key in ignore_entry_for:
                    return (
                        e.event_type == "entry"
                        and bool(e.is_inferred)
                        and str(reason) == "first_seen_inside"
                    )
                if e.track_key in ignore_exit_for:
                    return (
                        e.event_type == "exit"
                        and bool(e.is_inferred)
                        and str(reason) == "track_ended_inside"
                    )
                return False

            events_for_pairing = [e for e in emp_events if not _is_boundary_event(e)]

        # Punch-in priority: observed entry -> inferred entry -> None
        observed_entries = [
            e.ts for e in emp_events if e.event_type == "entry" and not e.is_inferred
        ]
        inferred_entries = [
            e.ts for e in emp_events if e.event_type == "entry" and e.is_inferred
        ]

        if observed_entries:
            punch_in = min(observed_entries)
            punch_in_is_inferred = False
        elif inferred_entries:
            punch_in = min(inferred_entries)
            punch_in_is_inferred = True
        else:
            punch_in = None
            punch_in_is_inferred = False

        # Punch-out priority: observed exit -> inferred exit -> None
        observed_exits = [
            e.ts for e in emp_events if e.event_type == "exit" and not e.is_inferred
        ]
        inferred_exits = [
            e.ts for e in emp_events if e.event_type == "exit" and e.is_inferred
        ]

        if observed_exits:
            punch_out = max(observed_exits)
            punch_out_is_inferred = False
        elif inferred_exits:
            punch_out = max(inferred_exits)
            punch_out_is_inferred = True
        else:
            punch_out = None
            punch_out_is_inferred = False

        sessions, anomalies = _pair_sessions(events_for_pairing)
        if stitched_groups:
            anomalies["stitched_tracklets"] = sum(len(g) for g in stitched_groups)
            anomalies["stitched_groups"] = len(stitched_groups)
        if punch_in is None and punch_out is None:
            anomalies = {"absent": True}
            total_minutes = 0
        else:
            # “missing_*” means “we did not OBSERVE a clean event”
            if punch_in is None or punch_in_is_inferred:
                anomalies["missing_entry"] = True
                if punch_in_is_inferred:
                    anomalies["inferred_entry"] = True

            if punch_out is None or punch_out_is_inferred:
                anomalies["missing_exit"] = True
                if punch_out_is_inferred:
                    anomalies["inferred_exit"] = True

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
