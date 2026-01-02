"""
identity.py

Goal:
- Assign `employee_id` to `tracks` and `events` using pgvector (employee_faces).

Important:
- In the real system, you’ll compute a face embedding from CCTV frames.
- For now (Phase 1 backend), we use a deterministic STUB track embedding so the
  end-to-end plumbing can be tested via Swagger without ML dependencies.

How the stub works:
- We compute a centroid embedding per employee (average of all templates).
- For each track_key, we deterministically pick one employee (hash(track_key) % N).
- We use that employee’s centroid as the "track embedding".
- Then we still run the REAL pgvector nearest-neighbor query to validate the DB/query flow.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.models import Employee, EmployeeFace, Event, Job, Track, Video


# TODO: Research on Frigate's face recognition implementation
@dataclass(frozen=True)
class IdentityConfig:
    """
    Thresholds are deliberately permissive by default because our stub embeddings
    are not "real face embeddings".

    TODO: When you plug in a real face model later, you should tighten:
    - max_cosine_distance ~ 0.25-0.40 (model dependent)
    - require_margin = True
    - min_margin ~ 0.02-0.08 (model dependent)
    """

    max_cosine_distance: float = 1.0
    require_margin: bool = False
    min_margin: float = 0.02


def _stable_int(value: str) -> int:
    """
    Deterministic integer from a string (used for stable mapping in the stub).
    """
    d = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(d[:4], "big")


def _mean_embedding(vectors: list[list[float]]) -> list[float]:
    """
    Compute centroid vector (element-wise mean).

    We do this in Python to avoid relying on pgvector aggregate extensions.
    """
    if not vectors:
        raise ValueError("Cannot compute mean of empty vectors")

    dim = len(vectors[0])
    acc = [0.0] * dim
    for v in vectors:
        if len(v) != dim:
            raise ValueError("Inconsistent embedding dimensions")
        for i in range(dim):
            acc[i] += float(v[i])

    n = float(len(vectors))
    return [x / n for x in acc]


def _load_employee_centroids(
    db: Session, *, store_id: UUID
) -> tuple[list[UUID], dict[UUID, list[float]]]:
    """
    Returns:
      employee_ids_sorted: list[UUID] (only employees with at least 1 face)
      centroids: dict[employee_id] -> embedding(list[float])
    """
    rows = (
        db.query(EmployeeFace.employee_id, EmployeeFace.embedding)
        .join(Employee, Employee.id == EmployeeFace.employee_id)
        .filter(Employee.store_id == store_id, Employee.is_active.is_(True))
        .all()
    )
    
    faces_by_emp: dict[UUID, list[list[float]]] = defaultdict(list)
    for emp_id, emb in rows:
        faces_by_emp[emp_id].append(emb)

    if not faces_by_emp:
        return [], {}

    centroids: dict[UUID, list[float]] = {}
    for emp_id, vecs in faces_by_emp.items():
        centroids[emp_id] = _mean_embedding(vecs)

    # Sort so mapping hash(track_key) % N stays stable
    employee_ids_sorted = sorted(centroids.keys(), key=lambda x: str(x))
    return employee_ids_sorted, centroids


def _make_track_embedding_stub(
    track_key: str,
    *,
    employee_ids: list[UUID],
    centroids: dict[UUID, list[float]],
) -> list[float] | None:
    """
    STUB: deterministically maps each track_key to one employee centroid.
    This gives stable "recognition" results during backend-only development.
    """
    if not employee_ids:
        return None

    idx = _stable_int(track_key) % len(employee_ids)
    target_emp_id = employee_ids[idx]
    return centroids[target_emp_id]


def _best_employee_match(
    db: Session,
    *,
    store_id: UUID,
    query_embedding: list[float],
) -> list[tuple[UUID, float]]:
    """
    Uses pgvector cosine distance.
    Returns up to 2 candidates: [(employee_id, distance), ...] sorted by distance asc.
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


def assign_identities_for_job(
    db: Session,
    *,
    job_id: UUID,
    cfg: IdentityConfig | None = None,
) -> dict[str, Any]:
    """
    Main entrypoint used by worker and optional API recompute endpoint.

    Updates:
    - tracks.employee_id / tracks.assigned_type / tracks.identity_confidence
    - events.employee_id (only where currently NULL)
    """
    cfg = cfg or IdentityConfig()

    job = db.get(Job, job_id)
    if job is None:
        raise RuntimeError("Job not found")

    video = db.get(Video, job.video_id)
    if video is None:
        raise RuntimeError("Video not found for job")

    store_id = video.store_id

    employee_ids, centroids = _load_employee_centroids(db, store_id=store_id)
    if not employee_ids:
        return {"assigned_tracks": 0, "skipped_no_faces": True}

    tracks = db.query(Track).filter(Track.job_id == job_id).all()
    
    assigned = 0
    for t in tracks:
        # Don’t overwrite if already assigned (use recompute endpoint to clear/rebuild if you want).
        if t.employee_id is not None:
            continue

        query_embedding = _make_track_embedding_stub(
            t.track_key, employee_ids=employee_ids, centroids=centroids
        )
        if query_embedding is None:
            continue

        candidates = _best_employee_match(
            db, store_id=store_id, query_embedding=query_embedding
        )
        if not candidates:
            continue

        best_emp_id, best_dist = candidates[0]
        second_dist = candidates[1][1] if len(candidates) > 1 else None
        
        # Acceptance rules (default permissive for stub; tighten later for real embeddings)
        if best_dist > cfg.max_cosine_distance:
            continue
        if cfg.require_margin and second_dist is not None:
            if (second_dist - best_dist) < cfg.min_margin:
                continue

        # Confidence mapping (simple UI-friendly score; tune later)
        identity_conf = max(0.0, 1.0 - best_dist)

        t.employee_id = best_emp_id
        t.assigned_type = "employee"
        t.identity_confidence = identity_conf
        db.add(t)

        # Update events for this track (don’t overwrite non-null employee_id)
        (
            db.query(Event)
            .filter(
                Event.job_id == job_id,
                Event.track_key == t.track_key,
                Event.employee_id.is_(None),
            )
            .update({Event.employee_id: best_emp_id}, synchronize_session=False)
        )
        
        assigned += 1

    db.commit()
    return {"assigned_tracks": assigned, "skipped_no_faces": False}
