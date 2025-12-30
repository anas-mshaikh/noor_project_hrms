from __future__ import annotations

from datetime import datetime
from typing import Iterable
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.models import Event, Track
from app.worker.event_engine import TrackDoorState, finalize_track, observe_track_point
from app.worker.zones import Zone, ZoneConfig

"""
pipeline_stub.py

A tiny synthetic pipeline so the rest of the backend can be exercised without
any CV dependencies.

- You feed it "frames" that already contain tracking IDs and bboxes.
- It converts bboxes -> foot point -> event engine.
- It writes rows into:
  - tracks
  - events

This is intentionally simple and heavily commented so you can swap it out later
with a real detector/tracker while keeping the same event/rollup logic.
"""


def _footpoint(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    # Bottom-center of bbox is more stable for door crossing
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, y2)


def process_tracks_stub(
    db: Session,
    *,
    job_id: UUID,
    frames: Iterable[
        tuple[datetime, list[tuple[str, tuple[float, float, float, float]]]]
    ],
    zone_cfg: ZoneConfig,
    default_employee_id: UUID | None = None,
) -> None:
    """
    Stub pipeline: consumes synthetic frames with tracked bboxes and emits events/tracks.

    frames: iterable of (ts, [ (track_key, bbox), ... ]) where bbox=(x1,y1,x2,y2)

    default_employee_id:
      For now we "pretend" face recognition matched this track to an employee.
      This is only to help you see attendance rollups in Swagger before CV is added.
    """
    door_states: dict[str, TrackDoorState] = {}

    # Track summary fields we persist at the end (1 row per track).
    track_first_ts: dict[str, datetime] = {}
    track_last_ts: dict[str, datetime] = {}
    track_first_zone: dict[str, Zone] = {}
    track_last_zone: dict[str, Zone] = {}

    # ----------------------------
    # Per-frame processing loop
    # ----------------------------
    for ts, detections in frames:
        for track_key, bbox in detections:
            point = _footpoint(bbox)

            state = door_states.setdefault(track_key, TrackDoorState())

            # Event engine returns (zone, optional DoorEvent).
            z, door_event = observe_track_point(
                state,
                point=point,
                ts=ts,
                zone_cfg=zone_cfg,
                # For Phase 1, default True is practical because attendance depends on events.
                infer_entry_on_first_seen_inside=True,
            )

            # Track summary bookkeeping.
            track_first_ts.setdefault(track_key, ts)
            track_first_zone.setdefault(track_key, z)
            track_last_ts[track_key] = ts
            track_last_zone[track_key] = z

            # IMPORTANT FIX:
            # Only write an Event row when the event engine actually emits an event.
            if door_event is None:
                continue

            db.add(
                Event(
                    id=uuid4(),
                    job_id=job_id,
                    ts=door_event.ts,  # can be earlier than `ts` for inferred entry
                    event_type=door_event.event_type.value,
                    entrance_id=None,
                    track_key=track_key,
                    employee_id=default_employee_id,
                    confidence=door_event.confidence,
                    snapshot_path=None,
                    is_inferred=door_event.is_inferred,
                    meta=door_event.meta,
                )
            )

    # ----------------------------
    # Track finalization (end-of-job)
    # ----------------------------
    # In a real tracker you'd finalize when a track disappears (TTL).
    # In the stub, we finalize at the end of all frames.
    for track_key, state in door_states.items():
        door_event = finalize_track(state, infer_exit_on_track_end=True)
        if door_event is None:
            continue

        db.add(
            Event(
                id=uuid4(),
                job_id=job_id,
                ts=door_event.ts,
                event_type=door_event.event_type.value,
                entrance_id=None,
                track_key=track_key,
                employee_id=default_employee_id,
                confidence=door_event.confidence,
                snapshot_path=None,
                is_inferred=door_event.is_inferred,
                meta=door_event.meta,
            )
        )

    # ----------------------------
    # Persist tracks (one row per track)
    # ----------------------------
    assigned_type = "employee" if default_employee_id is not None else "unknown"
    for track_key, first_ts in track_first_ts.items():
        db.add(
            Track(
                id=uuid4(),
                job_id=job_id,
                track_key=track_key,
                entrance_id=None,
                first_ts=first_ts,
                last_ts=track_last_ts[track_key],
                best_snapshot_path=None,
                assigned_type=assigned_type,
                employee_id=default_employee_id,
                identity_confidence=None,
                first_seen_zone=track_first_zone.get(track_key, Zone.UNKNOWN).value,
                last_seen_zone=track_last_zone.get(track_key, Zone.UNKNOWN).value,
            )
        )

    db.commit()
