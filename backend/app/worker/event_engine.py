from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.worker.zones import (
    Zone,
    ZoneConfig,
    classify_zone,
    is_in_gate,
    oriented_line_sign,
)

"""
event_engine.py

This module is responsible for *door semantics*.

Given a sequence of per-track observations (timestamp + point), we output
ENTRY/EXIT
events. This stays independent from any specific CV stack.

We explicitly separate:
- Observed events: we saw a clean crossing of the configured door line.
- Inferred events: we did NOT see a clean crossing, but the state strongly
suggests it
  (e.g., track becomes stably inside, or ends inside).

Why inference matters:
- CCTV tracking drops a lot (occlusion, motion blur).
- Employees can already be inside when the video starts.
- You still want a stable attendance record, but you want it labeled as
inferred.
"""


## TODO: Extensively research this module.


class EventType(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"


@dataclass(frozen=True)
class DoorEvent:
    """
    The worker writes this into the `events` table.

    - event_type: entry|exit
    - is_inferred:
        False => we observed strong evidence (line crossing)
        True  => we inferred it (start inside, end inside, or zone transition w/o line)
    - confidence: keep this simple for now; later you can compute real confidence
      from detector/tracker quality and face match.
    - meta: human/debug friendly info for exports and audits.
    """

    event_type: EventType
    ts: datetime
    is_inferred: bool
    confidence: float | None
    meta: dict[str, Any]


@dataclass
class TrackDoorState:
    # ----------------------------
    # Debounced zone state machine
    # ----------------------------
    stable_zone: Zone = Zone.UNKNOWN
    candidate_zone: Zone = Zone.UNKNOWN
    candidate_streak: int = 0

    # Cooldown prevents double events when the point jitters around the boundary.
    last_event_ts: datetime | None = None

    # ----------------------------
    # Track lifecycle timestamps
    # (used for inferred events)
    # ----------------------------
    first_seen_ts: datetime | None = None
    first_inside_ts: datetime | None = None
    last_seen_ts: datetime | None = None
    last_inside_ts: datetime | None = None

    # ----------------------------
    # Door line evidence
    # ----------------------------
    last_point: tuple[float, float] | None = None
    last_line_sign: int | None = None  # +1 inside side, -1 outside side (oriented)
    last_observed_crossing: tuple[EventType, datetime] | None = None

    # Gate evidence (helps ensure events happen "near the door")
    last_in_gate_ts: datetime | None = None


def _line_is_configured(cfg: ZoneConfig) -> bool:
    return (
        cfg.entry_line_p1 is not None
        and cfg.entry_line_p2 is not None
        and cfg.inside_test_point is not None
    )


def _in_cooldown(state: TrackDoorState, ts: datetime, cooldown_sec: float) -> bool:
    if state.last_event_ts is None:
        return False
    return (ts - state.last_event_ts).total_seconds() < cooldown_sec


def _recent_crossing_ts(
    state: TrackDoorState,
    expected: EventType,
    ts: datetime,
    window_sec: float,
) -> datetime | None:
    """
    Returns the crossing timestamp if we observed a matching line sign flip recently.
    """
    if state.last_observed_crossing is None:
        return None
    crossing_type, crossing_ts = state.last_observed_crossing
    if crossing_type != expected:
        return None
    if (ts - crossing_ts).total_seconds() > window_sec:
        return None
    return crossing_ts


def _recent_in_gate(state: TrackDoorState, ts: datetime, window_sec: float) -> bool:
    """
    True if we were inside the gate polygon recently.

    Why not check "in gate right now"?

    Debouncing means the stable zone transition can happen a few frames AFTER the
    actual crossing. By then, the person might already have walked past the gate.
    """
    if state.last_in_gate_ts is None:
        return False
    return (ts - state.last_in_gate_ts).total_seconds() <= window_sec


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
    Feed ONE observation (point at timestamp) for a track.

    Returns:
      observed_zone: Zone
      event: DoorEvent | None
    """
    # Track lifecycle timestamps (helps with inferred events).
    if state.first_seen_ts is None:
        state.first_seen_ts = ts
    state.last_seen_ts = ts

    # Gate evidence: even if you didn't configure gate, is_in_gate() returns True.
    if is_in_gate(point, zone_cfg):
        state.last_in_gate_ts = ts

    # Zone classification (INSIDE/OUTSIDE/UNKNOWN).
    observed_zone = classify_zone(point, zone_cfg)

    # Track inside timestamps (for "first seen inside" and "ended inside").
    if observed_zone == Zone.INSIDE:
        if state.first_inside_ts is None:
            state.first_inside_ts = ts
        state.last_inside_ts = ts

    # ----------------------------
    # Door line crossing detection
    # ----------------------------
    current_sign = oriented_line_sign(point, zone_cfg)
    if current_sign is not None:
        if state.last_line_sign is not None and current_sign != state.last_line_sign:
            # Sign flip implies the point crossed the line between last_point -> point.
            crossing_type = (
                EventType.ENTRY
                if state.last_line_sign == -1 and current_sign == 1
                else EventType.EXIT
            )

            # Only trust the crossing if it happened near the door region (gate).
            if is_in_gate(point, zone_cfg) or (
                state.last_point is not None and is_in_gate(state.last_point, zone_cfg)
            ):
                state.last_observed_crossing = (crossing_type, ts)

        # Only update last_line_sign when we're not in the neutral band.
        state.last_line_sign = current_sign

    # ----------------------------
    # Stable zone debouncing
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
    # Case 1: first stable zone establishment
    # ---------------------------------------
    if prev_zone == Zone.UNKNOWN:
        if new_zone != Zone.INSIDE:
            return observed_zone, None

        if _in_cooldown(state, ts, cooldown_sec):
            return observed_zone, None

        crossing_ts = _recent_crossing_ts(
            state, EventType.ENTRY, ts, crossing_window_sec
        )
        if crossing_ts is not None:
            state.last_event_ts = ts
            return observed_zone, DoorEvent(
                event_type=EventType.ENTRY,
                ts=crossing_ts,
                is_inferred=False,
                confidence=0.9,
                meta={
                    "reason": "line_crossing_first_stable_inside",
                    "from_zone": prev_zone.value,
                    "to_zone": new_zone.value,
                    "line_crossing_observed": True,
                },
            )

        if infer_entry_on_first_seen_inside:
            inferred_ts = state.first_inside_ts or state.first_seen_ts or ts
            state.last_event_ts = ts
            return observed_zone, DoorEvent(
                event_type=EventType.ENTRY,
                ts=inferred_ts,
                is_inferred=True,
                confidence=0.3,
                meta={
                    "reason": "first_seen_inside",
                    "from_zone": prev_zone.value,
                    "to_zone": new_zone.value,
                    "line_crossing_observed": False,
                },
            )

        return observed_zone, None

    # ---------------------------------------
    # Case 2: stable OUTSIDE <-> INSIDE change
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
            meta={
                "reason": "line_crossing",
                "from_zone": prev_zone.value,
                "to_zone": new_zone.value,
                "line_crossing_observed": True,
            },
        )

    # Inferred event if we were near the door recently.
    if line_configured and infer_transitions_without_line_crossing:
        if not _recent_in_gate(state, ts, crossing_window_sec):
            return observed_zone, None

        state.last_event_ts = ts
        return observed_zone, DoorEvent(
            event_type=expected,
            ts=ts,
            is_inferred=True,
            confidence=0.6,
            meta={
                "reason": "zone_transition_without_line_crossing",
                "from_zone": prev_zone.value,
                "to_zone": new_zone.value,
                "line_crossing_observed": False,
            },
        )

    # No line configured => zone transition is your only evidence.
    if not line_configured:
        state.last_event_ts = ts
        return observed_zone, DoorEvent(
            event_type=expected,
            ts=ts,
            is_inferred=False,
            confidence=0.8,
            meta={
                "reason": "zone_transition_no_line",
                "from_zone": prev_zone.value,
                "to_zone": new_zone.value,
                "line_crossing_observed": False,
            },
        )

    return observed_zone, None


def finalize_track(
    state: TrackDoorState,
    *,
    infer_exit_on_track_end: bool = True,
) -> DoorEvent | None:
    """
    Call this when a track disappears / the job ends.

    If the last stable zone is INSIDE, we likely missed the exit (occlusion/tracker drop).
    We infer an exit so attendance has punch_out, but it stays labeled inferred.
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
        meta={
            "reason": "track_ended_inside",
            "from_zone": Zone.INSIDE.value,
            "to_zone": Zone.UNKNOWN.value,
            "line_crossing_observed": False,
        },
    )


class EventType(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"


def update_door_state(
    state: TrackDoorState,
    observed_zone: Zone,
    ts: datetime,
    *,
    min_stable_frames: int = 3,
    cooldown_sec: float = 2.0,
) -> EventType | None:
    """
    Returns ENTRY/EXIT when a stable OUTSIDE→INSIDE or INSIDE→OUTSIDE transition occurs.
    Ignores UNKNOWN to reduce flicker near the line.
    """
    if observed_zone == Zone.UNKNOWN:
        return None

    if observed_zone == state.candidate_zone:
        state.candidate_streak += 1
    else:
        state.candidate_zone = observed_zone
        state.candidate_streak = 1

    if state.candidate_streak < min_stable_frames:
        return None

    new_zone = state.candidate_zone
    if new_zone == state.stable_zone:
        return None

    # First establishment of a stable zone: no event (avoids entry at t=0)
    if state.stable_zone == Zone.UNKNOWN:
        state.stable_zone = new_zone
        return None

    # Cooldown to avoid rapid toggles
    if (
        state.last_event_ts is not None
        and (ts - state.last_event_ts).total_seconds() < cooldown_sec
    ):
        state.stable_zone = new_zone
        return None

    evt: EventType | None = None
    if state.stable_zone == Zone.OUTSIDE and new_zone == Zone.INSIDE:
        evt = EventType.ENTRY
    elif state.stable_zone == Zone.INSIDE and new_zone == Zone.OUTSIDE:
        evt = EventType.EXIT

    state.stable_zone = new_zone
    if evt:
        state.last_event_ts = ts
    return evt
