"""
identity.py

Real identity assignment using pgvector (employee_faces).

Two use-cases:
1) Worker pipeline (online within job):
   - calls best_employee_candidates() + select_employee() while processing tracks

2) /jobs/{job_id}/recompute (offline):
   - re-assign identities from saved track snapshots (tracks.best_snapshot_path)
   - useful after you enroll more faces or adjust thresholds
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Employee, EmployeeFace, Event, Job, Track, Video


# TODO: Research on Frigate's face recognition implementation
@dataclass(frozen=True)
class IdentityConfig:
    """
    Acceptance rules for cosine distance.

    NOTE: These numbers are model-dependent.
    For InsightFace ArcFace-style embeddings, a good starting point is:
      max_cosine_distance ~ 0.30 - 0.45
      min_margin ~ 0.03 - 0.08
    """

    max_cosine_distance: float = 0.35
    require_margin: bool = True
    min_margin: float = 0.04


def store_has_enrolled_faces(db: Session, *, store_id: UUID) -> bool:
    """
    Quick check used to skip face-recognition work when no enrollment exists.
    """
    row = (
        db.query(EmployeeFace.id)
        .join(Employee, Employee.id == EmployeeFace.employee_id)
        .filter(Employee.store_id == store_id, Employee.is_active.is_(True))
        .limit(1)
        .first()
    )
    return row is not None


def best_employee_candidates(
    db: Session,
    *,
    store_id: UUID,
    query_embedding: list[float],
    limit: int = 2,
) -> list[tuple[UUID, float]]:
    """
    Uses pgvector cosine distance.
    Returns up to N candidates: [(employee_id, distance), ...] sorted by distance asc.

    We store many templates per employee, so we compute:
      distance(employee) = MIN distance among that employee's templates
    """
    dist_expr = EmployeeFace.embedding.cosine_distance(query_embedding)

    # We store many templates per employee, so we take MIN(distance) per employee.
    subq = (
        db.query(
            EmployeeFace.employee_id.label("employee_id"),
            sa.func.min(dist_expr).label("distance"),
        )
        .join(Employee, Employee.id == EmployeeFace.employee_id)
        .filter(Employee.store_id == store_id, Employee.is_active.is_(True))
        .group_by(EmployeeFace.employee_id)
        .subquery()
    )

    rows = (
        db.query(subq.c.employee_id, subq.c.distance)
        .order_by(subq.c.distance.asc())
        .limit(2)
        .all()
    )

    return [(row[0], float(row[1])) for row in rows]


def select_employee(
    candidates: list[tuple[UUID, float]],
    *,
    cfg: IdentityConfig,
) -> tuple[UUID, float, float] | None:
    """
    Apply threshold + margin rules and return:
      (employee_id, cosine_distance, confidence)
    """
    if not candidates:
        return None

    best_emp_id, best_dist = candidates[0]
    second_dist = candidates[1][1] if len(candidates) > 1 else None

    if best_dist > cfg.max_cosine_distance:
        return None

    if cfg.require_margin and second_dist is not None:
        if (second_dist - best_dist) < cfg.min_margin:
            return None

    confidence = max(0.0, 1.0 - best_dist)
    return best_emp_id, best_dist, confidence


def assign_identities_for_job(
    db: Session,
    *,
    job_id: UUID,
    cfg: IdentityConfig | None = None,
) -> dict[str, Any]:
    """
    Recompute identities for an existing job by reading saved snapshots:

    - For each track:
        - load tracks.best_snapshot_path
        - embed face
        - match via pgvector
        - update tracks + events (only where employee_id is NULL)

    This keeps /jobs/{job_id}/recompute REAL even after processing is done.
    """
    ccfg = cfg or IdentityConfig()

    job = db.get(Job, job_id)
    if job is None:
        raise RuntimeError("Job not found")

    video = db.get(Video, job.video_id)
    if video is None:
        raise RuntimeError("Video not found for job")

    store_id = video.store_id
    if not store_has_enrolled_faces(db, store_id=store_id):
        return {"assigned_tracks": 0, "skipped_no_faces": True}

    # Import heavy deps lazily (API server won't pay the cost unless endpoint is used).
    from app.worker.face_embedder import (  # local import on purpose
        FaceEmbedderError,
        get_face_embedder,
        read_image_bgr,
    )

    embedder = get_face_embedder()

    tracks = db.query(Track).filter(Track.job_id == job_id).all()

    assigned = 0
    for t in tracks:
        # We only assign if:
        # - we have a snapshot
        # - employee_id not already set
        if t.best_snapshot_path is None or t.employee_id is not None:
            continue

        img_path = (Path(settings.data_dir) / t.best_snapshot_path).resolve()
        if not img_path.exists():
            continue

        try:
            img = read_image_bgr(img_path)
            face = embedder.embed_best_face(img)
        except FaceEmbedderError:
            continue

        if face is None:
            continue

        candidates = best_employee_candidates(
            db, store_id=store_id, query_embedding=face.embedding, limit=2
        )
        chosen = select_employee(candidates, cfg=cfg)
        if chosen is None:
            continue

        emp_id, dist, confidence = chosen

        t.employee_id = emp_id
        t.assigned_type = "employee"
        t.identity_confidence = confidence
        db.add(t)

        # Update events for that track (do not overwrite non-null employee_id)
        (
            db.query(Event)
            .filter(
                Event.job_id == job_id,
                Event.track_key == t.track_key,
                Event.employee_id.is_(None),
            )
            .update({Event.employee_id: emp_id}, synchronize_session=False)
        )

        assigned += 1

    db.commit()
    return {"assigned_tracks": assigned, "skipped_no_faces": False}
