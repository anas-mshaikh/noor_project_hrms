from __future__ import annotations

"""
event_engine.py

Door event semantics (ENTRY/EXIT) based on:
- zone classification (inside/outside/unknown)
- optional oriented door line (strong evidence)
- optional gate polygon (only trust crossings near the doorway)
- debouncing + cooldown (prevents flicker/double events)

We also support *inferred* events:
- first_seen_inside -> inferred ENTRY (optional)
- track_ended_inside -> inferred EXIT (optional)

Worker writes these into the `events` table using:
- event_type: entry|exit
- is_inferred: true/false
- meta.reason: explanation string
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from app.worker.zones import Zone, ZoneConfig, classify_zone, is_in_gate, oriented_line_sign


class EventType(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"


@dataclass(frozen=True)
class DoorEvent:
    # What to insert into DB (events table)
    event_type: EventType
    ts: datetime
    is_inferred: bool
    confidence: float | None
    meta: dict[str, Any]


@dataclass
class TrackDoorState:
    # Debounced zone state
    stable_zone: Zone = Zone.UNKNOWN
    candidate_zone: Zone = Zone.UNKNOWN
    candidate_streak: int = 0

    # Cooldown to avoid rapid toggles / double counting
    last_event_ts: datetime | None = None

    # Track lifecycle timestamps (used for inference)
    first_seen_ts: datetime | None = None
    first_inside_ts: datetime | None = None
    last_seen_ts: datetime | None = None
    last_inside_ts: datetime | None = None

    # Line crossing evidence
    last_point: tuple[float, float] | None = None
    last_line_sign: int | None = None  # +1 inside side, -1 outside side
    last_observed_crossing: tuple[EventType, datetime] | None = None

    # Gate evidence (crossing must happen near the door)
    last_in_gate_ts: datetime | None = None


def _line_is_configured(cfg: ZoneConfig) -> bool:
    return (
        cfg.entry_line_p1 is not None
        and cfg.entry_line_p2 is not None
        and cfg.inside_test_point is not None
    )


def _in_cooldown(state: TrackDoorState, ts: datetime, cooldown_sec: float) -> bool:
    return (
        state.last_event_ts is not None
        and (ts - state.last_event_ts).total_seconds() < cooldown_sec
    )


def _recent_crossing_ts(
    state: TrackDoorState,
    expected: EventType,
    ts: datetime,
    window_sec: float,
) -> datetime | None:
    # Only trust a line sign flip that happened “recently”
    if state.last_observed_crossing is None:
        return None
    crossing_type, crossing_ts = state.last_observed_crossing
    if crossing_type != expected:
        return None
    if (ts - crossing_ts).total_seconds() > window_sec:
        return None
    return crossing_ts


def _recent_in_gate(state: TrackDoorState, ts: datetime, window_sec: float) -> bool:
    # Debouncing can delay stable state change, so check “recently in gate” instead of “in gate now”
    return (
        state.last_in_gate_ts is not None
        and (ts - state.last_in_gate_ts).total_seconds() <= window_sec
    )


def observe_track_point(
    state: TrackDoorState,
    *,
    point: tuple[float, float],
    ts: datetime,
    zone_cfg: ZoneConfig,
    min_stable_frames: int = 3,
    cooldown_sec: float = 2.0,
    crossing_window_sec: float = 2.0,
    infer_entry_on_first_seen_inside: bool = True,
    infer_transitions_without_line_crossing: bool = True,
) -> tuple[Zone, DoorEvent | None]:
    """
    Feed ONE observation (foot point at timestamp).

    Returns:
      (observed_zone, optional DoorEvent)
    """
    # Track lifecycle timestamps
    if state.first_seen_ts is None:
        state.first_seen_ts = ts
    state.last_seen_ts = ts

    # Gate evidence (even if gate not configured, is_in_gate() returns True)
    if is_in_gate(point, zone_cfg):
        state.last_in_gate_ts = ts

    # Zone classification
    observed_zone = classify_zone(point, zone_cfg)

    # Inside timestamps (used for inference)
    if observed_zone == Zone.INSIDE:
        if state.first_inside_ts is None:
            state.first_inside_ts = ts
        state.last_inside_ts = ts

    # ----------------------------
    # Door line crossing evidence
    # ----------------------------
    current_sign = oriented_line_sign(point, zone_cfg)
    if current_sign is not None:
        if state.last_line_sign is not None and current_sign != state.last_line_sign:
            # Line sign flip => crossed between last_point -> point
            crossing_type = (
                EventType.ENTRY
                if state.last_line_sign == -1 and current_sign == 1
                else EventType.EXIT
            )

            # Only trust crossings that happen near the door
            if is_in_gate(point, zone_cfg) or (
                state.last_point is not None and is_in_gate(state.last_point, zone_cfg)
            ):
                state.last_observed_crossing = (crossing_type, ts)

        state.last_line_sign = current_sign

    # Keep last point for “crossing near door” checks
    state.last_point = point

    # ----------------------------
    # Debounced stable zone switch
    # ----------------------------
    if observed_zone == Zone.UNKNOWN:
        return observed_zone, None

    if observed_zone == state.candidate_zone:
        state.candidate_streak += 1
    else:
        state.candidate_zone = observed_zone
        state.candidate_streak = 1

    if state.candidate_streak < min_stable_frames:
        return observed_zone, None

    new_zone = state.candidate_zone
    if new_zone == state.stable_zone:
        return observed_zone, None

    prev_zone = state.stable_zone
    state.stable_zone = new_zone

    # ---------------------------------------
    # Case A: first stable zone establishment
    # ---------------------------------------
    if prev_zone == Zone.UNKNOWN:
        # First stable OUTSIDE doesn't mean anything for attendance
        if new_zone != Zone.INSIDE:
            return observed_zone, None

        if _in_cooldown(state, ts, cooldown_sec):
            return observed_zone, None

        # If we saw a line crossing into inside, this is a strong observed ENTRY
        crossing_ts = _recent_crossing_ts(state, EventType.ENTRY, ts, crossing_window_sec)
        if crossing_ts is not None:
            state.last_event_ts = ts
            return observed_zone, DoorEvent(
                event_type=EventType.ENTRY,
                ts=crossing_ts,
                is_inferred=False,
                confidence=0.9,
                meta={"reason": "line_crossing_first_stable_inside"},
            )

        # Otherwise: track started inside (video start / missed earlier frames) => inferred ENTRY
        if infer_entry_on_first_seen_inside:
            inferred_ts = state.first_inside_ts or state.first_seen_ts or ts
            state.last_event_ts = ts
            return observed_zone, DoorEvent(
                event_type=EventType.ENTRY,
                ts=inferred_ts,
                is_inferred=True,
                confidence=0.3,
                meta={"reason": "first_seen_inside"},
            )

        return observed_zone, None

    # ---------------------------------------
    # Case B: stable OUTSIDE <-> INSIDE change
    # ---------------------------------------
    expected: EventType | None = None
    if prev_zone == Zone.OUTSIDE and new_zone == Zone.INSIDE:
        expected = EventType.ENTRY
    elif prev_zone == Zone.INSIDE and new_zone == Zone.OUTSIDE:
        expected = EventType.EXIT
    else:
        return observed_zone, None

    if _in_cooldown(state, ts, cooldown_sec):
        return observed_zone, None

    line_configured = _line_is_configured(zone_cfg)
    crossing_ts = _recent_crossing_ts(state, expected, ts, crossing_window_sec)

    if line_configured and crossing_ts is not None:
        state.last_event_ts = ts
        return observed_zone, DoorEvent(
            event_type=expected,
            ts=crossing_ts,
            is_inferred=False,
            confidence=0.9,
            meta={"reason": "line_crossing"},
        )

    # If we have a line but didn't see a clean crossing, we can infer *only if near door*
    if line_configured and infer_transitions_without_line_crossing:
        if not _recent_in_gate(state, ts, crossing_window_sec):
            return observed_zone, None

        state.last_event_ts = ts
        return observed_zone, DoorEvent(
            event_type=expected,
            ts=ts,
            is_inferred=True,
            confidence=0.6,
            meta={"reason": "zone_transition_without_line_crossing"},
        )

    # No line configured => zone transition is the evidence
    if not line_configured:
        state.last_event_ts = ts
        return observed_zone, DoorEvent(
            event_type=expected,
            ts=ts,
            is_inferred=False,
            confidence=0.8,
            meta={"reason": "zone_transition_no_line"},
        )

    return observed_zone, None


def finalize_track(
    state: TrackDoorState,
    *,
    infer_exit_on_track_end: bool = True,
) -> DoorEvent | None:
    """
    Call at track end (or end-of-job).

    If the track ended INSIDE, we likely missed the exit (occlusion/tracker drop),
    so we emit an inferred EXIT to stabilize attendance.
    """
    if not infer_exit_on_track_end:
        return None

    if state.stable_zone != Zone.INSIDE:
        return None

    ts = state.last_inside_ts or state.last_seen_ts
    if ts is None:
        return None

    return DoorEvent(
        event_type=EventType.EXIT,
        ts=ts,
        is_inferred=True,
        confidence=0.3,
        meta={"reason": "track_ended_inside"},
    )
