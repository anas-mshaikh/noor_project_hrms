"""
reliability.py

Pure helper logic for "attendance-first" reliability upgrades.

Why a separate module?
- It keeps pipeline.py readable.
- It makes behavior unit-testable without heavy video/model dependencies.

This module intentionally avoids importing:
- SQLAlchemy models
- OpenCV
- The face system
- Pydantic settings

The pipeline/rollup layers are responsible for wiring these helpers to real DB state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable, Sequence
from uuid import UUID


class DoorEventStrength(str, Enum):
    """
    STRONG:
      Evidence is high-confidence (e.g., line crossing).
      We commit immediately to avoid missing true attendance.

    MEDIUM:
      Evidence is plausible but not "hard" (e.g., zone transition without a line).
      Commit only after track stability.

    WEAK:
      Inference-only events (e.g., first_seen_inside, track_ended_inside).
      Commit only after track stability; drop pending ENTRY if the track dies early.
    """

    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


def classify_event_strength(reason: str | None) -> DoorEventStrength:
    """
    Convert event_engine meta.reason -> strength tier.

    We default to WEAK to stay conservative when new/unknown reasons appear.
    """
    if not reason:
        return DoorEventStrength.WEAK

    # Strongest: oriented line crossing evidence.
    if reason in {"line_crossing", "line_crossing_first_stable_inside"}:
        return DoorEventStrength.STRONG

    # Medium: no line configured, but zone transition is "real evidence".
    if reason in {"zone_transition_no_line"}:
        return DoorEventStrength.MEDIUM

    # Weak: inference-based or "no crossing but we guessed" transitions.
    if reason in {
        "first_seen_inside",
        "zone_transition_without_line_crossing",
        "track_ended_inside",
    }:
        return DoorEventStrength.WEAK

    return DoorEventStrength.WEAK


def is_track_stable(
    *,
    first_ts: datetime | None,
    now_ts: datetime,
    hits: int,
    min_age_sec: float,
    min_hits: int,
) -> bool:
    """
    Track stability gate used for flushing pending events.

    Attendance-first philosophy:
    - We prefer "late commit" over "false commit".
    - So we require either sufficient age OR sufficient number of detections (hits).
    """
    if hits >= int(min_hits):
        return True
    if first_ts is None:
        return False
    return (now_ts - first_ts).total_seconds() >= float(min_age_sec)


def should_commit_event(*, strength: DoorEventStrength, stable: bool) -> bool:
    """
    Two-phase commit rule:
    - STRONG commits immediately.
    - Everything else requires track stability.
    """
    if strength == DoorEventStrength.STRONG:
        return True
    return bool(stable)


@dataclass(frozen=True)
class PendingDoorEvent:
    """
    Event observed by event_engine, but not necessarily committed to DB yet.

    The pipeline must preserve the observed timestamp (ts) even if commit happens later.
    """

    event_type: str  # "entry" | "exit"
    ts: datetime
    is_inferred: bool
    confidence: float | None
    strength: DoorEventStrength
    snapshot_path: str | None
    meta: dict


def should_drop_pending_entry_on_end(event: PendingDoorEvent) -> bool:
    """
    If a track ends before it becomes stable, we drop WEAK/MEDIUM ENTRY events to avoid
    false punch-ins. STRONG ENTRY events must not be dropped.
    """
    if event.event_type != "entry":
        return False
    return event.strength != DoorEventStrength.STRONG


def exit_grace_expired(
    *,
    started_ts: datetime,
    now_ts: datetime,
    grace_sec: float,
) -> bool:
    """
    Exit grace window expiration check.
    """
    return (now_ts - started_ts).total_seconds() >= float(grace_sec)


def should_cancel_exit_pending(
    *,
    pending_employee_id: UUID | None,
    started_ts: datetime,
    now_ts: datetime,
    grace_sec: float,
    new_employee_id: UUID | None,
    new_lock_confidence: float | None,
    min_lock_score: float,
    new_in_door_roi: bool,
) -> bool:
    """
    Identity-aware cancel rule for exit_pending.

    Cancel only when:
    - pending track had a known employee_id
    - new track locks the same employee_id with high confidence
    - the new lock happens within grace window
    - and the new track is near the door (reduces risk of false continuity)
    """
    if pending_employee_id is None:
        return False
    if new_employee_id is None:
        return False
    if new_employee_id != pending_employee_id:
        return False
    if not new_in_door_roi:
        return False
    if new_lock_confidence is None or float(new_lock_confidence) < float(min_lock_score):
        return False
    if (now_ts - started_ts).total_seconds() > float(grace_sec):
        return False
    return True


@dataclass(frozen=True)
class Tracklet:
    """
    Minimal, rollup-friendly tracklet summary for conservative stitching decisions.
    """

    track_key: str
    employee_id: UUID
    lock_confidence: float
    start_ts: datetime
    end_ts: datetime
    first_zone: str | None
    last_zone: str | None


def _zone_is_inside(z: str | None) -> bool:
    return (z or "").lower() == "inside"


def find_unique_stitch_candidate(
    *,
    tracklets: Sequence[Tracklet],
    idx: int,
    gap_sec: float,
    min_lock_score: float,
    require_unique_candidate: bool,
    require_inside_continuity: bool = True,
) -> int | None:
    """
    Find a previous tracklet index to stitch with tracklets[idx].

    We only consider tracklets for the SAME employee_id and with high lock confidence.

    Uniqueness rule:
      If require_unique_candidate=True and there are 2+ possible previous candidates
      within the time window, we return None (too ambiguous).

    Zone continuity (conservative default):
      Require A ends INSIDE and B starts INSIDE. This is designed to repair false
      "track ended inside" exits + re-appearing inside, without accidentally merging
      real exit+re-entry.
    """
    if idx <= 0 or idx >= len(tracklets):
        return None

    b = tracklets[idx]
    if float(b.lock_confidence) < float(min_lock_score):
        return None

    candidates: list[int] = []
    for j in range(0, idx):
        a = tracklets[j]
        if a.employee_id != b.employee_id:
            continue
        if float(a.lock_confidence) < float(min_lock_score):
            continue
        if a.end_ts > b.start_ts:
            continue
        gap = (b.start_ts - a.end_ts).total_seconds()
        if gap < 0 or gap > float(gap_sec):
            continue
        if require_inside_continuity:
            if not (_zone_is_inside(a.last_zone) and _zone_is_inside(b.first_zone)):
                continue
        candidates.append(j)

    if not candidates:
        return None
    if require_unique_candidate and len(candidates) != 1:
        return None

    # Pick the closest-in-time candidate (largest end_ts).
    return max(candidates, key=lambda j: tracklets[j].end_ts)


def group_stitched_tracklets(
    *,
    tracklets: Sequence[Tracklet],
    gap_sec: float,
    min_lock_score: float,
    require_unique_candidate: bool,
    require_inside_continuity: bool = True,
) -> dict[str, str]:
    """
    Compute a mapping: track_key -> logical_session_id (string).

    The logical_session_id is a deterministic label used only for rollup grouping.
    We do NOT mutate tracker IDs or DB track_key values.
    """
    if not tracklets:
        return {}

    # Each track starts in its own session.
    session_of: dict[str, str] = {t.track_key: t.track_key for t in tracklets}

    for idx in range(len(tracklets)):
        cand = find_unique_stitch_candidate(
            tracklets=tracklets,
            idx=idx,
            gap_sec=gap_sec,
            min_lock_score=min_lock_score,
            require_unique_candidate=require_unique_candidate,
            require_inside_continuity=require_inside_continuity,
        )
        if cand is None:
            continue

        a = tracklets[cand]
        b = tracklets[idx]

        # Merge B's session into A's session.
        a_sess = session_of[a.track_key]
        b_sess = session_of[b.track_key]
        if a_sess == b_sess:
            continue

        # Repoint all keys currently in b_sess to a_sess.
        for k, sess in list(session_of.items()):
            if sess == b_sess:
                session_of[k] = a_sess

    return session_of


def iter_session_groups(mapping: dict[str, str]) -> Iterable[set[str]]:
    """
    Helper to turn track_key->session_id mapping into groups of track_keys.
    """
    by_session: dict[str, set[str]] = {}
    for track_key, session_id in mapping.items():
        by_session.setdefault(session_id, set()).add(track_key)
    return by_session.values()

