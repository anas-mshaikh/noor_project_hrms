"""
face_system

Frigate-style face recognition subsystem (CPU-first, offline-friendly).

High-level design goals:
- Separate face detection, alignment, and embedding (swap models easily).
- File-based "training library" of face images per employee.
- In-memory prototype embedding per employee (trimmed mean of embeddings).
- Runtime processor that votes across multiple frames per tracked person and "locks"
  identity for the track, so events/attendance can be attributed to an employee.

This package is designed to integrate with the existing worker video pipeline without
touching door logic (zones/line crossing). The pipeline can call:

  recognize_track_face(...)

to get an optional employee_id for the current track/frame.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import numpy as np


def recognize_track_face(
    frame_bgr: np.ndarray,
    person_bbox_xyxy: tuple[float, float, float, float],
    track_id: str,
    store_id: UUID,
    camera_id: UUID | None,
    ts: datetime,
):
    """
    Lazy wrapper to avoid importing heavy model/config code at package import time.

    Importing `app.face_system` should be cheap (and should not require env vars),
    so tests can import `app.face_system.utils` without needing DATABASE_URL, etc.
    """
    from app.face_system.runtime_processor import recognize_track_face as _impl

    return _impl(
        frame_bgr=frame_bgr,
        person_bbox_xyxy=person_bbox_xyxy,
        track_id=track_id,
        store_id=store_id,
        camera_id=camera_id,
        ts=ts,
    )


__all__ = ["recognize_track_face"]
