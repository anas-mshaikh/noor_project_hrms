"""
pipeline.py

REAL Phase 1 offline video pipeline (no stubs):

- Decode frames (sampled FPS)
- Motion gating on door ROI
- If ACTIVE (or heartbeat interval):
    - YOLO person detection + tracking
    - Line/zone door logic -> entry/exit events (event_engine.py)
    - Face recognition (gated): near door -> Frigate-style vote + lock (face_system)
- Persist:
    - events rows (+ snapshots at event frames)
    - tracks rows (+ best face snapshot path)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.face_system.config import FaceSystemConfig
from app.face_system.recognizer import FaceSystemError
from app.face_system.runtime_processor import FaceRuntimeProcessor
from app.face_system.storage import FaceLibraryStorage
from app.models.models import Event, Track, Video
from app.worker.detector_tracker import DetectorTracker
from app.worker.event_engine import TrackDoorState, finalize_track, observe_track_point
from app.worker.motion import MotionGate, MotionGateConfig, MotionState
from app.worker.reliability import (
    DoorEventStrength,
    PendingDoorEvent,
    classify_event_strength,
    exit_grace_expired,
    is_track_stable,
    should_cancel_exit_pending,
    should_commit_event,
    should_drop_pending_entry_on_end,
)
from app.worker.zones import Zone, ZoneConfig, is_in_gate, point_in_polygon


# NOTE: tune these later
@dataclass(frozen=True)
class PipelineConfig:
    # Frame sampling (trade speed vs accuracy)
    decode_fps: float = 8.0

    # Even when IDLE, run detector every N seconds (prevents missing slow motion)
    heartbeat_interval_sec: float = 2.0

    # Track finalization (if a track hasn't been seen in this many seconds)
    track_ttl_sec: float = 20.0

    # Motion gate tuning (ROI-aware)
    motion_thresh_fraction: float = 0.01
    motion_min_area_px: int = 800
    motion_consec_frames: int = 2
    active_hold_sec: float = 3.0

    # Event engine parameters
    zone_stable_frames: int = 3
    event_cooldown_sec: float = 2.0
    crossing_window_sec: float = 2.0
    infer_entry_on_first_seen_inside: bool = True
    infer_exit_on_track_end: bool = True
    infer_transitions_without_line_crossing: bool = True

    # Face recognition gating
    face_probe_cooldown_sec: float = 0.8
    face_max_probes: int = 8

    # Speed optimization: crop detection to door ROI bbox (if configured)
    use_door_roi_crop: bool = True

    # Snapshot debugging/auditing:
    # - Save a rolling "last seen" snapshot per track (overwritten file).
    # - Attach it to inferred exits (track_ended_inside) so the UI can show an image.
    save_last_seen_snapshots: bool = field(
        default_factory=lambda: bool(settings.save_last_seen_snapshots)
    )
    last_seen_snapshot_interval_sec: float = field(
        default_factory=lambda: float(settings.last_seen_snapshot_interval_sec)
    )
    attach_last_seen_snapshot_to_inferred_exit: bool = field(
        default_factory=lambda: bool(settings.attach_last_seen_snapshot_to_inferred_exit)
    )

    # -------------------------
    # Guardrails against false positives
    # -------------------------
    # Door cameras often have lots of clutter; YOLO can occasionally produce a tiny "person"
    # box on shoes/feet. Those boxes will never contain a face, but they CAN trigger
    # inferred entry/exit events via the door logic.
    #
    # We drop detections that are too small / too "square" to be a full person.
    min_person_bbox_height_px: int = 60  # absolute floor (px)
    min_person_bbox_height_frac: float = 0.10  # relative to frame height (0..1)
    min_person_bbox_aspect_ratio: float = 1.2  # height/width should look like a person

    # -------------------------
    # Attendance-first reliability upgrades (feature-flagged)
    # -------------------------
    # Two-phase commit for door events (PendingDoorEvent).
    enable_pending_events: bool = field(
        default_factory=lambda: bool(settings.enable_pending_events)
    )
    min_event_track_age_sec: float = field(
        default_factory=lambda: float(settings.min_event_track_age_sec)
    )
    min_event_track_hits: int = field(
        default_factory=lambda: int(settings.min_event_track_hits)
    )

    # Exit grace window (avoid false "track_ended_inside" exits).
    enable_exit_pending: bool = field(
        default_factory=lambda: bool(settings.enable_exit_pending)
    )
    exit_grace_sec: float = field(default_factory=lambda: float(settings.exit_grace_sec))

    # Recognized-only stitching (conservative).
    enable_recognized_stitching: bool = field(
        default_factory=lambda: bool(settings.enable_recognized_stitching)
    )
    stitch_gap_sec: float = field(default_factory=lambda: float(settings.stitch_gap_sec))
    stitch_min_lock_score: float = field(
        default_factory=lambda: float(settings.stitch_min_lock_score)
    )
    stitch_require_unique_candidate: bool = field(
        default_factory=lambda: bool(settings.stitch_require_unique_candidate)
    )

    @classmethod
    def from_job_config(cls, job_config: dict[str, Any] | None) -> "PipelineConfig":
        """
        Merge job.config_json overrides into defaults.

        Keep this strict-ish: unknown keys are ignored (so frontend can send extras safely).
        """
        data = dict(job_config or {})
        allowed = set(cls.__dataclass_fields__.keys())  # type: ignore[attr-defined]
        filtered: dict[str, Any] = {k: v for k, v in data.items() if k in allowed}

        return cls(**filtered)


@dataclass
class TrackRuntime:
    # Door event engine state
    door_state: TrackDoorState = field(default_factory=TrackDoorState)

    # Track summary
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    first_zone: Zone = Zone.UNKNOWN
    last_zone: Zone = Zone.UNKNOWN
    hits: int = 0  # number of detector updates for this track (stability proxy)

    # Best face snapshot (for audits + recompute)
    best_snapshot_path: str | None = None
    best_snapshot_quality: float = 0.0

    # Track-level debug snapshot (full-frame with bbox) updated periodically.
    # This lets us attach an image to inferred exits (track_ended_inside).
    last_seen_snapshot_path: str | None = None
    last_seen_snapshot_ts: datetime | None = None

    # Identity
    employee_id: UUID | None = None
    identity_confidence: float | None = None

    # Face probing (to limit compute; face_system has its own attempt caps too)
    probes: int = 0
    last_probe_ts: datetime | None = None

    # Last bbox (used for face crop)
    last_bbox: tuple[float, float, float, float] | None = None

    # -------------------------
    # Attendance-first reliability state
    # -------------------------
    # Door events are observed immediately but may be committed later (two-phase commit).
    pending_events: list[PendingDoorEvent] = field(default_factory=list)

    # Exit grace window:
    # when a track ends "inside", we delay inferred EXIT to avoid false punch-outs due to
    # short tracker dropouts/occlusions.
    exit_pending: bool = False
    exit_pending_started_ts: datetime | None = None
    exit_pending_exit_ts: datetime | None = None
    exit_pending_confidence: float | None = None
    exit_pending_meta: dict[str, Any] | None = None


def _safe_tz(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def _video_start_ts(video: Video, store_timezone: str) -> datetime:
    """
    Decide the timestamp for frame 0.

    Priority:
    1) video.recorded_start_ts (best)
    2) business_date midnight in store timezone (fallback)
    """
    tz = _safe_tz(store_timezone)

    ts = video.recorded_start_ts
    if ts is not None:
        # If user provided naive ts, assume store timezone (practical)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=tz)
        return ts.astimezone(timezone.utc)

    midnight_local = datetime.combine(video.business_date, time(0, 0), tzinfo=tz)
    return midnight_local.astimezone(timezone.utc)


def _footpoint(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    """
    Bottom-center point is usually the most stable for door crossing.
    """
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, y2)


def _snapshots_dir(job_id: UUID) -> Path:
    base = Path(settings.data_dir).resolve()
    return base / "jobs" / str(job_id) / "snapshots"


def _safe_name(value: str) -> str:
    """
    Make a filename-safe identifier.
    """
    out = []
    for ch in value:
        if ch.isalnum() or ch in {"-", "_"}:
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)


def _fmt_ts_for_filename(ts: datetime) -> str:
    # Compact + filesystem-friendly
    ts = ts.astimezone(timezone.utc)
    return ts.strftime("%Y%m%dT%H%M%S")


def _save_event_snapshot(
    *,
    job_id: UUID,
    track_key: str,
    ts: datetime,
    frame_bgr: np.ndarray,
    bbox: tuple[float, float, float, float] | None,
    label: str,
) -> str:
    """
    Save a full-frame snapshot with bbox overlay for auditing.
    Returns relative path stored in DB.
    """
    try:
        import cv2  # type: ignore
    except Exception as e:
        raise RuntimeError("opencv-python required for snapshot writing") from e

    base = Path(settings.data_dir).resolve()
    out_dir = base / "jobs" / str(job_id) / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_track = _safe_name(track_key)
    name = f"{label}_{safe_track}_{_fmt_ts_for_filename(ts)}.jpg"
    abs_path = out_dir / name

    img = frame_bgr.copy()

    if bbox is not None:
        x1, y1, x2, y2 = bbox
        cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 255), 2)

    cv2.putText(
        img,
        f"{label} {safe_track}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.imwrite(str(abs_path), img)

    # Store DB path relative to data_dir
    return str(abs_path.relative_to(Path(settings.data_dir).resolve()))


def _save_best_face_snapshot(
    *,
    job_id: UUID,
    track_key: str,
    face_crop_bgr: np.ndarray,
) -> str:
    """
    Save the best face crop for a track (overwrites when quality improves).
    Returns relative path stored in tracks.best_snapshot_path.
    """
    try:
        import cv2  # type: ignore
    except Exception as e:
        raise RuntimeError("opencv-python required for snapshot writing") from e

    base = Path(settings.data_dir).resolve()
    out_dir = base / "jobs" / str(job_id) / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_track = _safe_name(track_key)
    abs_path = out_dir / f"bestface_{safe_track}.jpg"

    cv2.imwrite(str(abs_path), face_crop_bgr)

    return str(abs_path.relative_to(Path(settings.data_dir).resolve()))


def _save_last_seen_snapshot(
    *,
    job_id: UUID,
    track_key: str,
    frame_bgr: np.ndarray,
    bbox: tuple[float, float, float, float] | None,
) -> str:
    """
    Save (overwrite) a "last seen" full-frame snapshot for a track.

    Why overwrite?
    - We want at most ONE file per track (avoid producing thousands of images).
    - Inferred exits happen after a grace window, when we no longer have a frame.
      This gives the UI something useful to inspect.
    """
    try:
        import cv2  # type: ignore
    except Exception as e:
        raise RuntimeError("opencv-python required for snapshot writing") from e

    base = Path(settings.data_dir).resolve()
    out_dir = base / "jobs" / str(job_id) / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_track = _safe_name(track_key)
    abs_path = out_dir / f"lastseen_{safe_track}.jpg"

    img = frame_bgr.copy()
    if bbox is not None:
        x1, y1, x2, y2 = bbox
        cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (255, 255, 0), 2)

    cv2.putText(
        img,
        f"last_seen {safe_track}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 0),
        2,
        cv2.LINE_AA,
    )

    cv2.imwrite(str(abs_path), img)

    return str(abs_path.relative_to(Path(settings.data_dir).resolve()))


def _polygon_bbox(
    poly: list[tuple[float, float]], w: int, h: int
) -> tuple[int, int, int, int]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x1 = max(0, min(int(min(xs)), w - 1))
    y1 = max(0, min(int(min(ys)), h - 1))
    x2 = max(0, min(int(max(xs)), w))
    y2 = max(0, min(int(max(ys)), h))
    return x1, y1, x2, y2


def process_video_pipeline(
    db: Session,
    *,
    job_id: UUID,
    video: Video,
    zone_cfg: ZoneConfig,
    store_timezone: str,
    cfg: PipelineConfig,
    on_progress: Callable[[int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """
    Main pipeline entrypoint used by tasks.py.

    Writes:
    - Event rows (entry/exit, inferred supported)
    - Track rows (per track summary)
    - Snapshot JPGs under data_dir/jobs/<job_id>/snapshots/
    """
    video_path = (Path(settings.data_dir) / video.file_path).resolve()
    if not video_path.exists():
        raise RuntimeError(f"Video file missing: {video_path}")

    try:
        import cv2  # type: ignore
    except Exception as e:
        raise RuntimeError("opencv-python is required to decode video") from e

    start_ts = _video_start_ts(video, store_timezone)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    try:
        # Use DB metadata if available; fall back to OpenCV.
        fps = float(video.fps or cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 0:
            fps = 25.0  # safe fallback

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        # Determine frame size
        w = int(video.width or cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(video.height or cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if w <= 0 or h <= 0:
            raise RuntimeError("Could not determine video width/height")

        # Sampling step
        target_fps = float(cfg.decode_fps)
        step = int(max(1, round(fps / target_fps))) if target_fps > 0 else 1

        # Motion gate uses door ROI if present, else gate, else full frame.
        # IMPORTANT: gate_polygon is often drawn tightly around the *floor/threshold*,
        # while door_roi_polygon should cover the full person area near the door.
        # We can safely use gate for motion (cheap), but we should NOT use it to crop
        # the YOLO detector input, otherwise YOLO will only "see" feet/legs.
        motion_roi = zone_cfg.door_roi or zone_cfg.gate
        motion_gate = MotionGate(
            frame_width=w,
            frame_height=h,
            door_roi=motion_roi,
            ignore_masks=zone_cfg.masks,
            cfg=MotionGateConfig(
                threshold_fraction=cfg.motion_thresh_fraction,
                min_area_px=cfg.motion_min_area_px,
                consec_frames=cfg.motion_consec_frames,
                active_hold_sec=cfg.active_hold_sec,
            ),
        )

        detector = DetectorTracker()

        # -------------------------
        # Face system (Frigate-style)
        # -------------------------
        # We create a job-scoped FaceRuntimeProcessor to avoid leaking track state across jobs.
        face_proc: FaceRuntimeProcessor | None = None
        face_cfg = FaceSystemConfig.from_settings()
        if face_cfg.enabled:
            storage = FaceLibraryStorage(face_cfg.storage)
            if storage.branch_has_any_images(tenant_id=video.tenant_id, branch_id=video.branch_id):
                # Fail fast if required model files are missing (better than silently producing
                # "all absent" attendance).
                if not face_cfg.detector.model_path.exists():
                    raise RuntimeError(
                        f"face detector model missing: {face_cfg.detector.model_path}"
                    )
                if not face_cfg.embedder.model_path.exists():
                    raise RuntimeError(
                        f"face embedding model missing: {face_cfg.embedder.model_path}"
                    )

                face_proc = FaceRuntimeProcessor(
                    tenant_id=video.tenant_id,
                    branch_id=video.branch_id,
                    camera_id=video.camera_id,
                )

                # Build prototypes once per job so runtime recognition doesn't race the async builder.
                face_proc.recognizer.ensure_built(block=True, timeout_sec=60.0)

        # Optional detection crop bbox (speed)
        crop_bbox: tuple[int, int, int, int] | None = None
        if cfg.use_door_roi_crop and zone_cfg.door_roi and len(zone_cfg.door_roi) >= 3:
            crop_bbox = _polygon_bbox(zone_cfg.door_roi, w, h)

        runtimes: dict[str, TrackRuntime] = {}
        # Tracker IDs can be reused; we must keep track_key unique per job.
        used_track_keys: set[str] = set()  # already written to DB (tracks)
        # Key by raw tracker id only so keys survive motion segment changes.
        reuse_count: dict[int, int] = {}  # raw_track_id -> n (reuse counter per job)
        active_key_by_raw: dict[int, str] = {}  # raw_track_id -> track_key while alive

        # For uniqueness and safety, prefix track keys by "segment id":
        # each time motion goes IDLE->ACTIVE we increment segment_id.
        segment_id = 0
        last_motion_state = MotionState.IDLE

        last_detector_ts: datetime | None = None
        last_progress_emit: int = -1

        inserts_since_commit = 0

        # Lightweight runtime metrics used for report.json (no DB schema changes).
        # Keep this JSON-serializable.
        reliability: dict[str, Any] = {
            "pending_events": {
                "enqueued": 0,
                "flushed": 0,
                "dropped": 0,
                "flush_latency_ms": [],  # list[float]; artifacts can bucketize
            },
            "exit_pending": {
                "started": 0,
                "canceled": 0,
                "expired_committed": 0,
            },
        }

        def _commit_event(
            *,
            track_key: str,
            rt: TrackRuntime,
            pe: PendingDoorEvent,
            committed_from_pending: bool,
            commit_ts: datetime,
        ) -> None:
            """
            Insert one Event row into the DB.

            IMPORTANT: We preserve the original observed timestamp (pe.ts) even if we commit later.
            """
            nonlocal inserts_since_commit

            db.add(
                Event(
                    id=uuid4(),
                    job_id=job_id,
                    ts=pe.ts,
                    event_type=pe.event_type,
                    entrance_id=None,
                    track_key=track_key,
                    employee_id=rt.employee_id,  # may still be None until locked
                    confidence=pe.confidence,
                    snapshot_path=pe.snapshot_path,
                    is_inferred=pe.is_inferred,
                    meta=pe.meta,
                )
            )
            inserts_since_commit += 1

            if committed_from_pending:
                reliability["pending_events"]["flushed"] += 1
                reliability["pending_events"]["flush_latency_ms"].append(
                    float((commit_ts - pe.ts).total_seconds() * 1000.0)
                )

        def _flush_pending_events_if_ready(*, track_key: str, rt: TrackRuntime, now_ts: datetime) -> None:
            """
            Flush pending events once a track becomes stable.

            We commit in timestamp order to preserve a sane event stream.
            """
            if not cfg.enable_pending_events:
                return
            if not rt.pending_events:
                return

            stable_now = is_track_stable(
                first_ts=rt.first_ts,
                now_ts=now_ts,
                hits=rt.hits,
                min_age_sec=float(cfg.min_event_track_age_sec),
                min_hits=int(cfg.min_event_track_hits),
            )
            if not stable_now:
                return

            for pe in sorted(rt.pending_events, key=lambda e: e.ts):
                _commit_event(
                    track_key=track_key,
                    rt=rt,
                    pe=pe,
                    committed_from_pending=True,
                    commit_ts=now_ts,
                )

            rt.pending_events.clear()

        def _finalize_track_runtime(*, track_key: str, rt: TrackRuntime, now_ts: datetime) -> None:
            """
            Persist Track summary and clean up in-memory state for this track_key.

            IMPORTANT: This does NOT emit any door events. Callers must insert any
            end-of-track events (observed/inferred) before finalizing if needed.
            """
            nonlocal inserts_since_commit

            db.add(
                Track(
                    id=uuid4(),
                    job_id=job_id,
                    track_key=track_key,
                    entrance_id=None,
                    first_ts=rt.first_ts or rt.last_ts or now_ts,
                    last_ts=rt.last_ts or now_ts,
                    best_snapshot_path=rt.best_snapshot_path,
                    assigned_type="employee" if rt.employee_id else "visitor",
                    employee_id=rt.employee_id,
                    identity_confidence=rt.identity_confidence,
                    first_seen_zone=rt.first_zone.value if rt.first_zone else None,
                    last_seen_zone=rt.last_zone.value if rt.last_zone else None,
                )
            )
            inserts_since_commit += 1

            if face_proc is not None:
                face_proc.end_track(track_key)

            del runtimes[track_key]
            used_track_keys.add(track_key)

            # Remove raw->key mapping for this finalized track key.
            for raw_id, key in list(active_key_by_raw.items()):
                if key == track_key:
                    del active_key_by_raw[raw_id]
                    break

        frame_idx = 0
        while True:
            # Cancellation (best-effort)
            if should_cancel is not None and should_cancel():
                break

            ok = cap.grab()
            if not ok:
                break

            if (frame_idx % step) != 0:
                frame_idx += 1
                continue

            ok, frame = cap.retrieve()
            if not ok or frame is None:
                break

            ts = start_ts + timedelta(seconds=float(frame_idx) / fps)
            frame_idx += 1

            # Motion gate (cheap, always)
            motion_state, _motion_area = motion_gate.update(frame, ts=ts)

            # Segment transitions
            if (
                last_motion_state == MotionState.IDLE
                and motion_state == MotionState.ACTIVE
            ):
                segment_id += 1
            last_motion_state = motion_state

            # Heartbeat: even in IDLE, run detector occasionally
            heartbeat_due = (
                last_detector_ts is None
                or (ts - last_detector_ts).total_seconds() >= cfg.heartbeat_interval_sec
            )

            has_active_tracks = any(
                rt.last_ts is not None
                and (ts - rt.last_ts).total_seconds() <= cfg.track_ttl_sec
                for rt in runtimes.values()
            )

            should_detect = (
                (motion_state == MotionState.ACTIVE)
                or heartbeat_due
                or has_active_tracks
            )
            if not should_detect:
                # Still emit progress occasionally
                if on_progress and total_frames > 0:
                    p = int((frame_idx / total_frames) * 90)
                    if p != last_progress_emit:
                        last_progress_emit = p
                        on_progress(p)
                continue

            last_detector_ts = ts

            # Detector input (possibly cropped)
            det_frame = frame
            offset_x = 0
            offset_y = 0
            if crop_bbox is not None:
                x1, y1, x2, y2 = crop_bbox
                det_frame = frame[y1:y2, x1:x2]
                offset_x, offset_y = x1, y1

            detections = detector.track(det_frame)
            # Tracks seen in this detector frame (used  for TTL cleanup)
            seen: set[str] = set()

            for d in detections:
                # Offset bbox back to full-frame coords
                x1, y1, x2, y2 = d.bbox_xyxy
                bbox = (x1 + offset_x, y1 + offset_y, x2 + offset_x, y2 + offset_y)

                # ---------------------------------------
                # Filter out tiny/invalid detections.
                #
                # If YOLO only sees a partial body (e.g. feet inside a cropped ROI),
                # it may output a small near-square box. Those boxes:
                # - produce "footpoints" that can trip door logic
                # - will never contain a face for recognition
                #
                # So we drop them early.
                # ---------------------------------------
                bw = float(bbox[2] - bbox[0])
                bh = float(bbox[3] - bbox[1])
                if bw <= 1.0 or bh <= 1.0:
                    continue

                min_h = max(
                    int(cfg.min_person_bbox_height_px),
                    int(float(cfg.min_person_bbox_height_frac) * float(h)),
                )
                if bh < float(min_h):
                    continue

                aspect = bh / max(bw, 1e-6)
                if aspect < float(cfg.min_person_bbox_aspect_ratio):
                    continue

                raw = int(d.track_id)

                # Reuse the same key while the track is alive.
                track_key = active_key_by_raw.get(raw)

                # If this is a "new" track lifecycle, allocate a unique key.
                if track_key is None:
                    base = f"t{d.track_id}"
                    n = reuse_count.get(raw, 0) + 1

                    while True:
                        candidate = base if n == 1 else f"{base}-r{n}"
                        if (
                            candidate not in used_track_keys
                            and candidate not in runtimes
                        ):
                            track_key = candidate
                            reuse_count[raw] = n
                            active_key_by_raw[raw] = track_key
                            break
                        n += 1

                seen.add(track_key)
                rt = runtimes.setdefault(track_key, TrackRuntime())
                rt.last_bbox = bbox

                # Periodically update "last seen" snapshot for this track (overwrites).
                # This is intentionally independent of door events so we can attach a snapshot
                # to inferred exits later.
                if cfg.save_last_seen_snapshots:
                    interval = float(cfg.last_seen_snapshot_interval_sec)
                    should_write = (
                        rt.last_seen_snapshot_ts is None
                        or interval <= 0.0
                        or (ts - rt.last_seen_snapshot_ts).total_seconds() >= interval
                    )
                    if should_write:
                        rt.last_seen_snapshot_ts = ts
                        rt.last_seen_snapshot_path = _save_last_seen_snapshot(
                            job_id=job_id,
                            track_key=track_key,
                            frame_bgr=frame,
                            bbox=bbox,
                        )

                # If this track was in "exit pending" state and reappeared, cancel the pending exit.
                if cfg.enable_exit_pending and rt.exit_pending:
                    rt.exit_pending = False
                    rt.exit_pending_started_ts = None
                    rt.exit_pending_exit_ts = None
                    rt.exit_pending_confidence = None
                    rt.exit_pending_meta = None
                    reliability["exit_pending"]["canceled"] += 1

                if rt.first_ts is None:
                    rt.first_ts = ts
                rt.last_ts = ts
                rt.hits += 1

                # Door logic uses foot point
                pt = _footpoint(bbox)

                # Track stability gate (attendance-first):
                # we allow "late commit" of door events, but we want to avoid committing
                # weak/inferred entries for 1-2 frame ghost tracks.
                stable_now = is_track_stable(
                    first_ts=rt.first_ts,
                    now_ts=ts,
                    hits=rt.hits,
                    min_age_sec=float(cfg.min_event_track_age_sec),
                    min_hits=int(cfg.min_event_track_hits),
                )

                observed_zone, door_event = observe_track_point(
                    rt.door_state,
                    point=pt,
                    ts=ts,
                    zone_cfg=zone_cfg,
                    min_stable_frames=cfg.zone_stable_frames,
                    cooldown_sec=cfg.event_cooldown_sec,
                    crossing_window_sec=cfg.crossing_window_sec,
                    infer_entry_on_first_seen_inside=cfg.infer_entry_on_first_seen_inside,
                    infer_transitions_without_line_crossing=cfg.infer_transitions_without_line_crossing,
                )

                if rt.first_zone == Zone.UNKNOWN:
                    rt.first_zone = observed_zone
                rt.last_zone = observed_zone

                # -------------------------
                # Emit entry/exit event
                # -------------------------
                if door_event is not None:
                    # Save snapshot for anything we observed WITH a frame in hand.
                    # (track_ended_inside is emitted in finalize, so no frame.)
                    snap = _save_event_snapshot(
                        job_id=job_id,
                        track_key=track_key,
                        ts=ts,
                        frame_bgr=frame,
                        bbox=bbox,
                        label=door_event.event_type.value,
                    )

                    meta = {
                        **(door_event.meta or {}),
                        "track_id": int(d.track_id),
                        "segment_id": int(segment_id),
                        "zone": observed_zone.value,
                        "bbox": [
                            float(bbox[0]),
                            float(bbox[1]),
                            float(bbox[2]),
                            float(bbox[3]),
                        ],
                    }
                    reason = str((door_event.meta or {}).get("reason", "") or "")
                    strength = classify_event_strength(reason)

                    pe = PendingDoorEvent(
                        event_type=door_event.event_type.value,
                        ts=door_event.ts,
                        is_inferred=bool(door_event.is_inferred),
                        confidence=door_event.confidence,
                        strength=strength,
                        snapshot_path=snap,
                        meta=meta,
                    )

                    if not cfg.enable_pending_events:
                        _commit_event(
                            track_key=track_key,
                            rt=rt,
                            pe=pe,
                            committed_from_pending=False,
                            commit_ts=ts,
                        )
                    else:
                        # Two-phase commit:
                        # - STRONG evidence (line crossing) commits immediately.
                        # - MEDIUM/WEAK commit only after track stabilization.
                        if should_commit_event(strength=strength, stable=stable_now):
                            _commit_event(
                                track_key=track_key,
                                rt=rt,
                                pe=pe,
                                committed_from_pending=False,
                                commit_ts=ts,
                            )
                        else:
                            rt.pending_events.append(pe)
                            reliability["pending_events"]["enqueued"] += 1

                # Flush any previously pending events once the track is stable.
                _flush_pending_events_if_ready(track_key=track_key, rt=rt, now_ts=ts)

                # -------------------------
                # Face recognition (gated)
                # -------------------------
                if face_proc is None:
                    continue  # no training faces => skip all identity work

                if rt.employee_id is not None:
                    continue  # already locked identity

                if rt.probes >= cfg.face_max_probes:
                    continue

                # Probe near door:
                # - if footpoint is in door ROI OR in gate polygon
                in_roi = False
                if zone_cfg.door_roi and len(zone_cfg.door_roi) >= 3:
                    in_roi = point_in_polygon(pt, zone_cfg.door_roi)
                else:
                    in_roi = is_in_gate(pt, zone_cfg)

                # Also probe when an event happened (usually right at the door)
                should_probe = in_roi or (door_event is not None)
                if not should_probe:
                    continue

                if rt.last_probe_ts is not None:
                    if (
                        ts - rt.last_probe_ts
                    ).total_seconds() < cfg.face_probe_cooldown_sec:
                        continue

                rt.probes += 1
                rt.last_probe_ts = ts

                try:
                    face_res = face_proc.process(
                        track_id=track_key,
                        frame_bgr=frame,
                        person_bbox_xyxy=bbox,
                        ts=ts,
                    )
                except FaceSystemError:
                    # Most likely: no prototypes built yet (e.g. missing training images).
                    # We skip this probe and continue processing events/tracks.
                    continue
                except Exception as e:
                    # Model/runtime errors should surface clearly for debugging.
                    raise RuntimeError(f"face recognition failed: {e}") from e

                # Save best face crop snapshot for audits (optional but very useful).
                # We compute a small "quality" metric similar to the legacy code:
                # - size (area) + blur (sharpness)
                face_crop = face_res.face_crop_bgr
                if (
                    face_crop is not None
                    and face_res.face_area is not None
                    and face_res.blur_score is not None
                ):
                    area = float(face_res.face_area)
                    blur = float(face_res.blur_score)
                    size_score = min(1.0, area / float(80.0 * 80.0))
                    blur_score = min(1.0, blur / 150.0)
                    quality = float(size_score * blur_score)

                    if quality > rt.best_snapshot_quality:
                        rt.best_snapshot_quality = quality
                        rt.best_snapshot_path = _save_best_face_snapshot(
                            job_id=job_id,
                            track_key=track_key,
                            face_crop_bgr=face_crop,
                        )

                # If face_system locked identity for this track, attach it.
                if face_res.locked and face_res.employee_id is not None:
                    rt.employee_id = face_res.employee_id
                    rt.identity_confidence = (
                        float(face_res.confidence)
                        if face_res.confidence is not None
                        else None
                    )

                    # IMPORTANT: our SessionLocal uses autoflush=False, so any Events inserted earlier
                    # in this loop (same frame) are not visible to the UPDATE below unless we flush.
                    # Without this, you can end up with:
                    # - entry event gets employee_id (updated later)
                    # - exit event inserted in the same frame stays NULL forever
                    #   because we only run this UPDATE once (when the track locks).
                    db.flush()

                    # Update previous events for this track (best-effort).
                    (
                        db.query(Event)
                        .filter(
                            Event.job_id == job_id,
                            Event.track_key == track_key,
                            Event.employee_id.is_(None),
                        )
                        .update(
                            {Event.employee_id: rt.employee_id},
                            synchronize_session=False,
                        )
                    )

                    # -------------------------
                    # Exit-pending identity-aware cancel
                    # -------------------------
                    # If another track "ended inside" recently (exit_pending) but this new track
                    # locks to the SAME employee near the door, treat it as continuity and
                    # finalize the old track WITHOUT emitting an inferred exit.
                    if (
                        cfg.enable_exit_pending
                        and observed_zone == Zone.INSIDE
                        and in_roi
                        and rt.identity_confidence is not None
                    ):
                        candidates: list[tuple[str, datetime]] = []
                        for other_tk, other_rt in runtimes.items():
                            if other_tk == track_key:
                                continue
                            if not other_rt.exit_pending:
                                continue
                            if other_rt.exit_pending_started_ts is None:
                                continue
                            if should_cancel_exit_pending(
                                pending_employee_id=other_rt.employee_id,
                                started_ts=other_rt.exit_pending_started_ts,
                                now_ts=ts,
                                grace_sec=float(cfg.exit_grace_sec),
                                new_employee_id=rt.employee_id,
                                new_lock_confidence=rt.identity_confidence,
                                min_lock_score=float(cfg.stitch_min_lock_score),
                                new_in_door_roi=True,
                            ):
                                candidates.append((other_tk, other_rt.exit_pending_started_ts))

                        if candidates:
                            # Ambiguity guard: require a unique candidate if enabled.
                            if cfg.stitch_require_unique_candidate and len(candidates) != 1:
                                candidates = []

                        if candidates:
                            chosen_tk, _started = max(candidates, key=lambda x: x[1])
                            old_rt = runtimes.get(chosen_tk)
                            if old_rt is not None:
                                reliability["exit_pending"]["canceled"] += 1
                                _finalize_track_runtime(
                                    track_key=chosen_tk, rt=old_rt, now_ts=ts
                                )

            # -------------------------
            # TTL finalization (tracks that disappeared)
            # Only do this on detector frames (so we don't finalize during skipped frames).
            # -------------------------
            now_ts = ts
            ttl = float(cfg.track_ttl_sec)
            to_finalize = []
            for tk, rt in runtimes.items():
                if tk in seen:
                    continue
                if rt.last_ts is None:
                    continue
                if (now_ts - rt.last_ts).total_seconds() > ttl:
                    to_finalize.append(tk)

            for tk in to_finalize:
                rt = runtimes[tk]

                # -------------------------
                # Exit pending grace handling
                # -------------------------
                if cfg.enable_exit_pending and rt.exit_pending:
                    # Waiting for grace window to expire (or cancel by reappearance/identity).
                    started_ts = rt.exit_pending_started_ts or now_ts
                    rt.exit_pending_started_ts = started_ts

                    if exit_grace_expired(
                        started_ts=started_ts,
                        now_ts=now_ts,
                        grace_sec=float(cfg.exit_grace_sec),
                    ):
                        # Finalize any still-pending door events.
                        # IMPORTANT: do NOT treat "time spent in grace" as extra track age.
                        # Use the last-seen timestamp for stability decisions.
                        if cfg.enable_pending_events and rt.pending_events:
                            stable_ref_ts = rt.last_ts or now_ts
                            stable_end = is_track_stable(
                                first_ts=rt.first_ts,
                                now_ts=stable_ref_ts,
                                hits=rt.hits,
                                min_age_sec=float(cfg.min_event_track_age_sec),
                                min_hits=int(cfg.min_event_track_hits),
                            )
                            if stable_end:
                                for pe in sorted(rt.pending_events, key=lambda e: e.ts):
                                    _commit_event(
                                        track_key=tk,
                                        rt=rt,
                                        pe=pe,
                                        committed_from_pending=True,
                                        commit_ts=now_ts,
                                    )
                            else:
                                for pe in rt.pending_events:
                                    if should_drop_pending_entry_on_end(pe):
                                        reliability["pending_events"]["dropped"] += 1
                                        continue
                                    if pe.strength == DoorEventStrength.STRONG:
                                        _commit_event(
                                            track_key=tk,
                                            rt=rt,
                                            pe=pe,
                                            committed_from_pending=True,
                                            commit_ts=now_ts,
                                        )
                            rt.pending_events.clear()

                        # Grace expired: commit inferred EXIT using the last-known inside timestamp.
                        exit_ts = rt.exit_pending_exit_ts or rt.last_ts or now_ts

                        db.add(
                            Event(
                                id=uuid4(),
                                job_id=job_id,
                                ts=exit_ts,
                                event_type="exit",
                                entrance_id=None,
                                track_key=tk,
                                employee_id=rt.employee_id,
                                confidence=rt.exit_pending_confidence,
                                snapshot_path=(
                                    rt.last_seen_snapshot_path
                                    if cfg.attach_last_seen_snapshot_to_inferred_exit
                                    else None
                                ),
                                is_inferred=True,
                                meta={
                                    **(rt.exit_pending_meta or {"reason": "track_ended_inside"}),
                                    "grace_sec": float(cfg.exit_grace_sec),
                                    "committed_after_grace": True,
                                },
                            )
                        )
                        inserts_since_commit += 1
                        reliability["exit_pending"]["expired_committed"] += 1

                        _finalize_track_runtime(track_key=tk, rt=rt, now_ts=now_ts)

                    # Not expired yet => keep runtime around.
                    continue

                # Decide whether this track end should enter exit_pending (ended inside).
                end_event = finalize_track(
                    rt.door_state, infer_exit_on_track_end=cfg.infer_exit_on_track_end
                )
                wants_exit_pending = (
                    cfg.enable_exit_pending
                    and end_event is not None
                    and bool(end_event.is_inferred)
                    and str((end_event.meta or {}).get("reason", "")) == "track_ended_inside"
                )

                # -------------------------
                # Two-phase commit: flush/drop pending events at track end.
                # -------------------------
                if cfg.enable_pending_events and rt.pending_events:
                    # IMPORTANT: use last-seen timestamp so "time spent missing" doesn't
                    # artificially make an unstable track look stable.
                    stable_ref_ts = rt.last_ts or now_ts
                    stable_end = is_track_stable(
                        first_ts=rt.first_ts,
                        now_ts=stable_ref_ts,
                        hits=rt.hits,
                        min_age_sec=float(cfg.min_event_track_age_sec),
                        min_hits=int(cfg.min_event_track_hits),
                    )

                    if stable_end:
                        for pe in sorted(rt.pending_events, key=lambda e: e.ts):
                            _commit_event(
                                track_key=tk,
                                rt=rt,
                                pe=pe,
                                committed_from_pending=True,
                                commit_ts=now_ts,
                            )
                        rt.pending_events.clear()
                    else:
                        # If we're going to hold the track in exit_pending, do NOT drop pending
                        # entries yet (the track may reappear/continue).
                        if not wants_exit_pending:
                            for pe in rt.pending_events:
                                if should_drop_pending_entry_on_end(pe):
                                    reliability["pending_events"]["dropped"] += 1
                                    continue
                                if pe.strength == DoorEventStrength.STRONG:
                                    _commit_event(
                                        track_key=tk,
                                        rt=rt,
                                        pe=pe,
                                        committed_from_pending=True,
                                        commit_ts=now_ts,
                                    )
                            rt.pending_events.clear()

                if wants_exit_pending:
                    # Start grace window: do NOT commit inferred exit yet.
                    rt.exit_pending = True
                    rt.exit_pending_started_ts = now_ts
                    rt.exit_pending_exit_ts = end_event.ts if end_event is not None else None
                    rt.exit_pending_confidence = (
                        float(end_event.confidence) if end_event and end_event.confidence is not None else None
                    )
                    rt.exit_pending_meta = dict(end_event.meta or {}) if end_event is not None else None
                    reliability["exit_pending"]["started"] += 1
                    continue

                # No exit grace needed: commit inferred exit immediately (legacy behavior).
                if end_event is not None:
                    snapshot_path: str | None = None
                    if (
                        cfg.attach_last_seen_snapshot_to_inferred_exit
                        and end_event.event_type.value == "exit"
                        and bool(end_event.is_inferred)
                    ):
                        snapshot_path = rt.last_seen_snapshot_path

                    db.add(
                        Event(
                            id=uuid4(),
                            job_id=job_id,
                            ts=end_event.ts,
                            event_type=end_event.event_type.value,
                            entrance_id=None,
                            track_key=tk,
                            employee_id=rt.employee_id,
                            confidence=end_event.confidence,
                            snapshot_path=snapshot_path,
                            is_inferred=end_event.is_inferred,
                            meta=end_event.meta,
                        )
                    )
                    inserts_since_commit += 1

                _finalize_track_runtime(track_key=tk, rt=rt, now_ts=now_ts)

            # Commit periodically so long jobs don't hold huge transactions
            if inserts_since_commit >= 200:
                db.commit()
                inserts_since_commit = 0

            # Progress (0..90 here; tasks.py will take it to 95/100)
            if on_progress and total_frames > 0:
                p = int((frame_idx / total_frames) * 90)
                if p != last_progress_emit:
                    last_progress_emit = p
                    on_progress(p)

        # End of video: finalize all remaining tracks
        now_ts = start_ts + timedelta(seconds=float(frame_idx) / fps)
        for tk, rt in list(runtimes.items()):
            # Flush/drop pending door events at end-of-video (same logic as TTL finalization).
            if cfg.enable_pending_events and rt.pending_events:
                stable_ref_ts = rt.last_ts or now_ts
                stable_end = is_track_stable(
                    first_ts=rt.first_ts,
                    now_ts=stable_ref_ts,
                    hits=rt.hits,
                    min_age_sec=float(cfg.min_event_track_age_sec),
                    min_hits=int(cfg.min_event_track_hits),
                )

                if stable_end:
                    for pe in sorted(rt.pending_events, key=lambda e: e.ts):
                        _commit_event(
                            track_key=tk,
                            rt=rt,
                            pe=pe,
                            committed_from_pending=True,
                            commit_ts=now_ts,
                        )
                    rt.pending_events.clear()
                else:
                    for pe in rt.pending_events:
                        if should_drop_pending_entry_on_end(pe):
                            reliability["pending_events"]["dropped"] += 1
                            continue
                        if pe.strength == DoorEventStrength.STRONG:
                            _commit_event(
                                track_key=tk,
                                rt=rt,
                                pe=pe,
                                committed_from_pending=True,
                                commit_ts=now_ts,
                            )
                    rt.pending_events.clear()

            # If the track is currently in exit_pending, we must force-commit the inferred EXIT
            # at end-of-video (there is no future frame where it can reappear).
            if cfg.enable_exit_pending and rt.exit_pending:
                exit_ts = rt.exit_pending_exit_ts or rt.last_ts or now_ts
                db.add(
                    Event(
                        id=uuid4(),
                        job_id=job_id,
                        ts=exit_ts,
                        event_type="exit",
                        entrance_id=None,
                        track_key=tk,
                        employee_id=rt.employee_id,
                        confidence=rt.exit_pending_confidence,
                        snapshot_path=(
                            rt.last_seen_snapshot_path
                            if cfg.attach_last_seen_snapshot_to_inferred_exit
                            else None
                        ),
                        is_inferred=True,
                        meta={
                            **(rt.exit_pending_meta or {"reason": "track_ended_inside"}),
                            "grace_sec": float(cfg.exit_grace_sec),
                            "committed_at_end_of_video": True,
                        },
                    )
                )
                inserts_since_commit += 1
                reliability["exit_pending"]["expired_committed"] += 1

                _finalize_track_runtime(track_key=tk, rt=rt, now_ts=now_ts)
                continue

            end_event = finalize_track(
                rt.door_state, infer_exit_on_track_end=cfg.infer_exit_on_track_end
            )
            if end_event is not None:
                snapshot_path: str | None = None
                if (
                    cfg.attach_last_seen_snapshot_to_inferred_exit
                    and end_event.event_type.value == "exit"
                    and bool(end_event.is_inferred)
                ):
                    snapshot_path = rt.last_seen_snapshot_path

                db.add(
                    Event(
                        id=uuid4(),
                        job_id=job_id,
                        ts=end_event.ts,
                        event_type=end_event.event_type.value,
                        entrance_id=None,
                        track_key=tk,
                        employee_id=rt.employee_id,
                        confidence=end_event.confidence,
                        snapshot_path=snapshot_path,
                        is_inferred=end_event.is_inferred,
                        meta=end_event.meta,
                    )
                )
                inserts_since_commit += 1

            _finalize_track_runtime(track_key=tk, rt=rt, now_ts=now_ts)

        db.commit()

        return {
            "frames_seen": int(frame_idx),
            "video_path": str(video_path),
            "used_face_recognition": bool(face_proc is not None),
            "reliability": reliability,
        }

    finally:
        cap.release()
