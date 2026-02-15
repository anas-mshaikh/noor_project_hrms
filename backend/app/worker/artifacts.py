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
from app.models.models import Artifact, Event, Job, Track, Video
from app.worker.reliability import Tracklet, group_stitched_tracklets, iter_session_groups


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


def write_job_artifacts(
    db: Session,
    *,
    job_id: UUID,
    pipeline_report: dict[str, object] | None = None,
) -> list[Artifact]:
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
    rows = db.execute(
        sa.text(
            """
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
                AND ee.end_date IS NULL
            ),
            ce AS (
              SELECT * FROM current_employment WHERE rn = 1
            ),
            employees AS (
              SELECT
                e.id AS employee_id,
                e.employee_code AS employee_code,
                (p.first_name || ' ' || p.last_name) AS employee_name
              FROM ce
              JOIN hr_core.employees e ON e.id = ce.employee_id
              JOIN hr_core.persons p ON p.id = e.person_id
              WHERE ce.branch_id = :branch_id
                AND e.tenant_id = :tenant_id
                AND e.status = 'ACTIVE'
            )
            SELECT
              employees.employee_id,
              employees.employee_code,
              employees.employee_name,
              ad.punch_in,
              ad.punch_out,
              ad.total_minutes,
              ad.anomalies_json
            FROM employees
            LEFT JOIN attendance.attendance_daily ad
              ON ad.tenant_id = :tenant_id
             AND ad.branch_id = :branch_id
             AND ad.business_date = :business_date
             AND ad.employee_id = employees.employee_id
            ORDER BY employees.employee_code, employees.employee_id
            """
        ),
        {
            "tenant_id": video.tenant_id,
            "branch_id": video.branch_id,
            "business_date": video.business_date,
        },
    ).all()

    with attendance_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "tenant_id",
                "branch_id",
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

        for r in rows:
            punch_in = r.punch_in.isoformat() if r.punch_in else ""
            punch_out = r.punch_out.isoformat() if r.punch_out else ""
            total_minutes = "" if r.total_minutes is None else int(r.total_minutes)
            anomalies = r.anomalies_json or {"absent": True}

            writer.writerow(
                {
                    "tenant_id": str(video.tenant_id),
                    "branch_id": str(video.branch_id),
                    "business_date": video.business_date.isoformat(),
                    "employee_id": str(r.employee_id),
                    "employee_code": str(r.employee_code),
                    "employee_name": str(r.employee_name or "").strip(),
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

    # Derived metrics (DB-backed, recomputable).
    total_events = len(events)
    events_with_employee = sum(1 for e in events if e.employee_id is not None)
    inferred_events = sum(1 for e in events if e.is_inferred)

    employee_id_coverage = (
        (events_with_employee / total_events) if total_events > 0 else None
    )
    inferred_ratio = (inferred_events / total_events) if total_events > 0 else None

    tracks = (
        db.query(Track)
        .filter(Track.job_id == job_id, Track.employee_id.isnot(None))
        .all()
    )
    tracks_with_employee = len(tracks)
    unique_employees_locked = len({t.employee_id for t in tracks if t.employee_id is not None})
    track_fragmentation = (
        (tracks_with_employee / unique_employees_locked)
        if unique_employees_locked > 0
        else None
    )

    # Conservative stitch stats (best-effort, for reporting only).
    stitched_groups_total = 0
    stitched_track_keys_total = 0
    if bool(settings.enable_recognized_stitching) and tracks:
        by_emp: dict[UUID, list[Tracklet]] = {}
        for t in tracks:
            if t.employee_id is None or t.identity_confidence is None:
                continue
            by_emp.setdefault(t.employee_id, []).append(
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
        for tls in by_emp.values():
            tls = sorted(tls, key=lambda x: x.start_ts)
            mapping = group_stitched_tracklets(
                tracklets=tls,
                gap_sec=float(settings.stitch_gap_sec),
                min_lock_score=float(settings.stitch_min_lock_score),
                require_unique_candidate=bool(settings.stitch_require_unique_candidate),
                require_inside_continuity=True,
            )
            groups = [g for g in iter_session_groups(mapping) if len(g) > 1]
            stitched_groups_total += len(groups)
            stitched_track_keys_total += sum(len(g) for g in groups)

    # Pipeline-provided runtime counters (best-effort).
    # Note: pipeline_report is optional (e.g. recompute endpoints may call artifacts directly).
    reliability: dict[str, object] = {}
    if isinstance(pipeline_report, dict):
        rel = pipeline_report.get("reliability")
        if isinstance(rel, dict):
            reliability = rel

    # Extract/sanitize pending stats (avoid writing huge arrays into report.json).
    pending_stats_raw = reliability.get("pending_events") if isinstance(reliability, dict) else None
    if not isinstance(pending_stats_raw, dict):
        pending_stats_raw = {}

    pending_enqueued = int(pending_stats_raw.get("enqueued", 0) or 0)
    pending_flushed = int(pending_stats_raw.get("flushed", 0) or 0)
    pending_dropped = int(pending_stats_raw.get("dropped", 0) or 0)

    exit_pending_raw = reliability.get("exit_pending") if isinstance(reliability, dict) else None
    if not isinstance(exit_pending_raw, dict):
        exit_pending_raw = {}

    # Summarize flush latency into small buckets (avoid huge report.json).
    latency_buckets: dict[str, int] = {}
    try:
        latencies = []
        raw_lat = pending_stats_raw.get("flush_latency_ms")
        if isinstance(raw_lat, list):
            latencies = [float(x) for x in raw_lat if isinstance(x, (int, float))]
        # Buckets in milliseconds.
        edges = [0.0, 250.0, 1000.0, 5000.0]
        labels = ["<=0ms", "<=250ms", "<=1s", "<=5s", ">5s"]
        counts = [0, 0, 0, 0, 0]
        for ms in latencies:
            if ms <= edges[0]:
                counts[0] += 1
            elif ms <= edges[1]:
                counts[1] += 1
            elif ms <= edges[2]:
                counts[2] += 1
            elif ms <= edges[3]:
                counts[3] += 1
            else:
                counts[4] += 1
        latency_buckets = {labels[i]: int(counts[i]) for i in range(len(labels))}
    except Exception:
        latency_buckets = {}

    report = {
        "job_id": str(job.id),
        "video_id": str(video.id),
        "tenant_id": str(video.tenant_id),
        "branch_id": str(video.branch_id),
        "camera_id": str(video.camera_id),
        "business_date": video.business_date.isoformat(),
        "generated_at": _utcnow_iso(),
        "counts": {
            "events": total_events,
            "entries": sum(1 for e in events if e.event_type == "entry"),
            "exits": sum(1 for e in events if e.event_type == "exit"),
            "inferred": inferred_events,
        },
        "metrics": {
            "employee_id_coverage": employee_id_coverage,
            "inferred_ratio": inferred_ratio,
            "track_fragmentation": track_fragmentation,
            "tracks_with_employee": tracks_with_employee,
            "unique_employees_locked": unique_employees_locked,
            "stitched_groups_total": stitched_groups_total,
            "stitched_track_keys_total": stitched_track_keys_total,
        },
        "reliability": {
            "pending_events": {
                "enqueued": pending_enqueued,
                "flushed": pending_flushed,
                "dropped": pending_dropped,
            },
            "pending_event_flush_latency_buckets_ms": latency_buckets,
            "exit_pending": exit_pending_raw,
        },
        "discrepancy_check": {
            "detection_continuity_when_tracks_exist": True,
            "track_key_job_global": True,
            "notes": "These checks reflect configured code paths, not runtime verification.",
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
