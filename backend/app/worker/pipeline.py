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

    # -------------------------
    # Guardrails against false positives
    # -------------------------
    # Door cameras often have lots of clutter; YOLO can occasionally produce a tiny "person"
    # box on shoes/feet. Those boxes will never contain a face, but they CAN trigger
    # inferred entry/exit events via the door logic.
    #
    # We drop detections that are too small / too "square" to be a full person.
    min_person_bbox_height_px: int = 60          # absolute floor (px)
    min_person_bbox_height_frac: float = 0.10    # relative to frame height (0..1)
    min_person_bbox_aspect_ratio: float = 1.2    # height/width should look like a person

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

    # Best face snapshot (for audits + recompute)
    best_snapshot_path: str | None = None
    best_snapshot_quality: float = 0.0

    # Identity
    employee_id: UUID | None = None
    identity_confidence: float | None = None

    # Face probing (to limit compute; face_system has its own attempt caps too)
    probes: int = 0
    last_probe_ts: datetime | None = None

    # Last bbox (used for face crop)
    last_bbox: tuple[float, float, float, float] | None = None


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
            if storage.store_has_any_images(store_id=video.store_id):
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
                    store_id=video.store_id,
                    camera_id=video.camera_id,
                )

                # Build prototypes once per job so runtime recognition doesn't race the async builder.
                face_proc.recognizer.ensure_built(block=True, timeout_sec=60.0)

        # Optional detection crop bbox (speed)
        crop_bbox: tuple[int, int, int, int] | None = None
        if (
            cfg.use_door_roi_crop
            and zone_cfg.door_roi
            and len(zone_cfg.door_roi) >= 3
        ):
            crop_bbox = _polygon_bbox(zone_cfg.door_roi, w, h)

        runtimes: dict[str, TrackRuntime] = {}
        # Tracker IDs can be reused; we must keep track_key unique per job.
        used_track_keys: set[str] = set()  # already written to DB (tracks)
        reuse_count: dict[tuple[int, int], int] = {}  # (segment_id, raw_track_id) -> n
        active_key_by_raw: dict[
            tuple[int, int], str
        ] = {}  # current mapping while track is alive

        # For uniqueness and safety, prefix track keys by "segment id":
        # each time motion goes IDLE->ACTIVE we increment segment_id.
        segment_id = 0
        last_motion_state = MotionState.IDLE

        last_detector_ts: datetime | None = None
        last_progress_emit: int = -1

        inserts_since_commit = 0
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

            should_detect = (motion_state == MotionState.ACTIVE) or heartbeat_due
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

                raw = (int(segment_id), int(d.track_id))

                # Reuse the same key while the track is alive.
                track_key = active_key_by_raw.get(raw)

                # If this is a "new" track lifecycle, allocate a unique key.
                if track_key is None:
                    base = f"s{segment_id}-t{d.track_id}"
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

                if rt.first_ts is None:
                    rt.first_ts = ts
                rt.last_ts = ts

                # Door logic uses foot point
                pt = _footpoint(bbox)

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

                    db.add(
                        Event(
                            id=uuid4(),
                            job_id=job_id,
                            ts=door_event.ts,
                            event_type=door_event.event_type.value,
                            entrance_id=None,
                            track_key=track_key,
                            employee_id=rt.employee_id,  # might be None until recognized
                            confidence=door_event.confidence,
                            snapshot_path=snap,
                            is_inferred=door_event.is_inferred,
                            meta={
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
                            },
                        )
                    )
                    inserts_since_commit += 1

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
                        float(face_res.confidence) if face_res.confidence is not None else None
                    )

                    # Update previous events for this track (best-effort).
                    (
                        db.query(Event)
                        .filter(
                            Event.job_id == job_id,
                            Event.track_key == track_key,
                            Event.employee_id.is_(None),
                        )
                        .update(
                            {Event.employee_id: rt.employee_id}, synchronize_session=False
                        )
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

                # Inferred EXIT if ended INSIDE
                end_event = finalize_track(
                    rt.door_state, infer_exit_on_track_end=cfg.infer_exit_on_track_end
                )
                if end_event is not None:
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
                            snapshot_path=None,
                            is_inferred=end_event.is_inferred,
                            meta=end_event.meta,
                        )
                    )
                    inserts_since_commit += 1

                # Persist track summary
                db.add(
                    Track(
                        id=uuid4(),
                        job_id=job_id,
                        track_key=tk,
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
                    face_proc.end_track(tk)
                del runtimes[tk]
                used_track_keys.add(tk)

                # Remove raw->key mapping for this finalized track key
                for k, v in list(active_key_by_raw.items()):
                    if v == tk:
                        del active_key_by_raw[k]
                        break

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
            end_event = finalize_track(
                rt.door_state, infer_exit_on_track_end=cfg.infer_exit_on_track_end
            )
            if end_event is not None:
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
                        snapshot_path=None,
                        is_inferred=end_event.is_inferred,
                        meta=end_event.meta,
                    )
                )

            db.add(
                Track(
                    id=uuid4(),
                    job_id=job_id,
                    track_key=tk,
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
            if face_proc is not None:
                face_proc.end_track(tk)
            used_track_keys.add(tk)
            for k, v in list(active_key_by_raw.items()):
                if v == tk:
                    del active_key_by_raw[k]
                    break
            del runtimes[tk]

        db.commit()

        return {
            "frames_seen": int(frame_idx),
            "video_path": str(video_path),
            "used_face_recognition": bool(face_proc is not None),
        }

    finally:
        cap.release()
