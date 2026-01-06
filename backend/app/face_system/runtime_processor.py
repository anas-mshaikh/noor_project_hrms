"""
runtime_processor.py

Frigate-style per-track runtime face recognition:
- Detect faces inside a tracked person's crop.
- Align, embed, classify using store prototypes.
- Maintain attempt history and vote across frames.
- "Lock" the identity for a track when confidence is stable enough.

This module provides the minimal integration hook expected by the worker pipeline:

  recognize_track_face(frame_bgr, person_bbox, track_id, store_id, camera_id) -> UUID | None

The pipeline can also construct FaceRuntimeProcessor directly for more control
(e.g. job-scoped state).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import UUID

import numpy as np

from app.face_system.config import FaceSystemConfig
from app.face_system.detector.opencv_yn import OpenCVYNFaceDetector
from app.face_system.embedders.insightface_arcface import ONNXArcFaceEmbedder
from app.face_system.aligners.opencv_lbf import OpenCVLBFFaceAligner
from app.face_system.recognizer import FaceRecognizer, FaceRecognizeResult, FaceSystemError
from app.face_system.storage import FaceLibraryStorage
from app.face_system.utils import (
    BBox,
    blur_score_laplacian_var,
    expand_upward_bbox,
    safe_basename,
    vote_weighted_identity,
)


@dataclass(frozen=True)
class FaceAttempt:
    ts: datetime
    employee_id: UUID | None  # None => unknown
    confidence: float
    face_area: int


@dataclass
class TrackFaceState:
    """
    Runtime state for a single track.
    """

    locked_employee_id: UUID | None = None
    locked_confidence: float | None = None
    attempts: list[FaceAttempt] = field(default_factory=list)
    attempts_total: int = 0
    attempts_after_lock: int = 0


@dataclass(frozen=True)
class TrackFaceResult:
    employee_id: UUID | None
    confidence: float | None
    locked: bool
    meta: dict[str, Any]
    # Best-effort debug fields for the caller (e.g. worker pipeline).
    # These are intentionally NOT persisted by the face system itself; the pipeline
    # can decide whether/how to save snapshots.
    face_crop_bgr: np.ndarray | None = None
    face_area: int | None = None
    blur_score: float | None = None


class FaceRuntimeProcessor:
    def __init__(self, *, store_id: UUID, camera_id: UUID | None = None) -> None:
        self.cfg = FaceSystemConfig.from_settings()
        self.store_id = store_id
        self.camera_id = camera_id

        if not self.cfg.enabled:
            raise FaceSystemError("face system disabled")

        self.storage = FaceLibraryStorage(self.cfg.storage)
        self.detector = OpenCVYNFaceDetector(self.cfg.detector)
        self.aligner = OpenCVLBFFaceAligner(self.cfg.aligner)
        self.embedder = ONNXArcFaceEmbedder(self.cfg.embedder)
        self.recognizer = FaceRecognizer(
            store_id=store_id,
            detector_cfg=self.cfg.detector,
            aligner_cfg=self.cfg.aligner,
            embedder_cfg=self.cfg.embedder,
            recognizer_cfg=self.cfg.recognizer,
            storage=self.storage,
        )

        self._lock = Lock()
        self._tracks: dict[str, TrackFaceState] = {}

    def reset(self) -> None:
        """
        Clear per-track state (useful between jobs).
        """
        with self._lock:
            self._tracks = {}

    def end_track(self, track_id: str) -> None:
        """
        Remove track state to prevent memory growth.
        """
        with self._lock:
            self._tracks.pop(track_id, None)

    # -------------------------
    # Core per-frame processing
    # -------------------------
    def process(
        self,
        *,
        track_id: str,
        frame_bgr: np.ndarray,
        person_bbox_xyxy: tuple[float, float, float, float],
        ts: datetime,
    ) -> TrackFaceResult:
        """
        Attempt recognition for one tracked person at one timestamp.

        Returns:
        - employee_id (locked if available)
        - confidence (best/locked)
        - meta info for debugging
        """
        with self._lock:
            st = self._tracks.setdefault(track_id, TrackFaceState())

        # If already locked, optionally stop attempting.
        if st.locked_employee_id is not None:
            if st.attempts_after_lock >= int(self.cfg.runtime.max_attempts_after_lock):
                return TrackFaceResult(
                    employee_id=st.locked_employee_id,
                    confidence=st.locked_confidence,
                    locked=True,
                    meta={"reason": "already_locked"},
                )

        if st.attempts_total >= int(self.cfg.runtime.max_face_attempts):
            return TrackFaceResult(
                employee_id=st.locked_employee_id,
                confidence=st.locked_confidence,
                locked=st.locked_employee_id is not None,
                meta={"reason": "attempt_cap_reached"},
            )

        # Crop person region (expand upward to include head)
        h, w = frame_bgr.shape[:2]
        person_bbox = expand_upward_bbox(
            person_bbox_xyxy,
            frame_w=w,
            frame_h=h,
            pad_px=int(self.cfg.runtime.pad_px),
            expand_upward_frac=float(self.cfg.runtime.expand_upward_frac),
        )
        x1, y1, x2, y2 = person_bbox.as_xyxy()
        person_crop = frame_bgr[y1:y2, x1:x2].copy()
        if person_crop.size == 0:
            return TrackFaceResult(
                employee_id=st.locked_employee_id,
                confidence=st.locked_confidence,
                locked=st.locked_employee_id is not None,
                meta={"reason": "empty_person_crop"},
            )

        # Detect face inside person crop.
        face_det = self.detector.detect_best(person_crop)
        if face_det is None:
            st.attempts_total += 1
            return TrackFaceResult(
                employee_id=st.locked_employee_id,
                confidence=st.locked_confidence,
                locked=st.locked_employee_id is not None,
                meta={"reason": "no_face_detected"},
            )

        fx1, fy1, fx2, fy2 = face_det.bbox_xyxy
        face_bbox = BBox(fx1, fy1, fx2, fy2).clamp(w=person_crop.shape[1], h=person_crop.shape[0])
        if face_bbox.area() < int(self.cfg.runtime.min_face_area):
            st.attempts_total += 1
            return TrackFaceResult(
                employee_id=st.locked_employee_id,
                confidence=st.locked_confidence,
                locked=st.locked_employee_id is not None,
                meta={"reason": "face_too_small", "face_area": face_bbox.area()},
                face_area=int(face_bbox.area()),
            )

        face_crop = person_crop[face_bbox.y1:face_bbox.y2, face_bbox.x1:face_bbox.x2].copy()
        if face_crop.size == 0:
            st.attempts_total += 1
            return TrackFaceResult(
                employee_id=st.locked_employee_id,
                confidence=st.locked_confidence,
                locked=st.locked_employee_id is not None,
                meta={"reason": "empty_face_crop"},
            )

        blur = float(blur_score_laplacian_var(face_crop))

        # Align (optional, fallback allowed by config)
        aligned = self.aligner.align(face_crop)
        if aligned is None:
            if not bool(self.cfg.aligner.allow_unaligned_fallback):
                st.attempts_total += 1
                return TrackFaceResult(
                    employee_id=st.locked_employee_id,
                    confidence=st.locked_confidence,
                    locked=st.locked_employee_id is not None,
                    meta={"reason": "alignment_failed"},
                    face_crop_bgr=face_crop,
                    face_area=int(face_bbox.area()),
                    blur_score=blur,
                )
            aligned = face_crop

        # Embed
        try:
            emb = self.embedder.embed(aligned)
        except Exception as e:
            st.attempts_total += 1
            return TrackFaceResult(
                employee_id=st.locked_employee_id,
                confidence=st.locked_confidence,
                locked=st.locked_employee_id is not None,
                meta={"reason": "embed_failed", "error": str(e)},
                face_crop_bgr=face_crop,
                face_area=int(face_bbox.area()),
                blur_score=blur,
            )

        try:
            rec = self.recognizer.recognize_embedding(
                emb, blur_score=blur, top_k=5
            )
        except FaceSystemError as e:
            st.attempts_total += 1
            return TrackFaceResult(
                employee_id=st.locked_employee_id,
                confidence=st.locked_confidence,
                locked=st.locked_employee_id is not None,
                meta={"reason": "recognizer_error", "error": str(e)},
                face_crop_bgr=face_crop,
                face_area=int(face_bbox.area()),
                blur_score=blur,
            )

        st.attempts_total += 1
        if st.locked_employee_id is not None:
            st.attempts_after_lock += 1

        attempt = FaceAttempt(
            ts=ts,
            employee_id=rec.employee_id,
            confidence=float(rec.confidence),
            face_area=int(face_bbox.area()),
        )
        st.attempts.append(attempt)

        # Optional debug artifact saving.
        if bool(self.cfg.runtime.save_attempts):
            self._save_attempt_debug(
                track_id=track_id,
                ts=ts,
                face_crop_bgr=face_crop,
                label=str(rec.employee_id) if rec.employee_id else "unknown",
                score=float(rec.confidence),
            )

        # Voting / locking.
        winner = self._vote_for_track(st)
        if winner is not None:
            emp_id, score = winner
            if st.locked_employee_id is None:
                st.locked_employee_id = emp_id
                st.locked_confidence = float(score)
            return TrackFaceResult(
                employee_id=st.locked_employee_id,
                confidence=st.locked_confidence,
                locked=True,
                meta={"reason": "locked", "winner_score": float(score)},
                face_crop_bgr=face_crop,
                face_area=int(face_bbox.area()),
                blur_score=blur,
            )

        return TrackFaceResult(
            employee_id=st.locked_employee_id,
            confidence=st.locked_confidence,
            locked=st.locked_employee_id is not None,
            meta={
                "reason": "not_locked",
                "latest_employee_id": str(rec.employee_id) if rec.employee_id else None,
                "latest_confidence": float(rec.confidence),
            },
            face_crop_bgr=face_crop,
            face_area=int(face_bbox.area()),
            blur_score=blur,
        )

    def _vote_for_track(self, st: TrackFaceState) -> tuple[UUID, float] | None:
        """
        Frigate-style weighted voting.

        Rules from task spec:
        - ignore unknown
        - weight = min(face_area, 4000)
        - weight *= (score - unknown_score) * 10
        - require min_faces attempts for winner
        - if tie in counts => return None
        """
        return vote_weighted_identity(
            ((a.employee_id, a.confidence, a.face_area) for a in st.attempts),
            unknown_score=float(self.cfg.recognizer.unknown_score),
            min_faces=int(self.cfg.runtime.min_faces_for_lock),
            threshold=float(self.cfg.runtime.recognition_threshold),
        )

    def _save_attempt_debug(
        self,
        *,
        track_id: str,
        ts: datetime,
        face_crop_bgr: np.ndarray,
        label: str,
        score: float,
    ) -> None:
        """
        Save face crops for debugging (optional).
        """
        import cv2  # type: ignore

        # Store under <DATA_DIR>/faces/train (matches spec "backend/data/faces/train/").
        root = self.storage.face_dir
        out_dir = root / "train"
        out_dir.mkdir(parents=True, exist_ok=True)

        safe_track = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in track_id)
        safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in label)
        name = f"{safe_track}-{ts.strftime('%Y%m%dT%H%M%S')}-{safe_label}-{score:.3f}.jpg"
        cv2.imwrite(str(out_dir / name), face_crop_bgr)


# -----------------------------------------------------------------------------
# Minimal hook API for the existing worker pipeline
# -----------------------------------------------------------------------------

_PROCESSORS: dict[tuple[UUID, UUID | None], FaceRuntimeProcessor] = {}
_PROC_LOCK = Lock()


def get_runtime_processor(*, store_id: UUID, camera_id: UUID | None = None) -> FaceRuntimeProcessor:
    """
    Process-level cache for processors (heavy models + prototypes).
    """
    key = (store_id, camera_id)
    with _PROC_LOCK:
        proc = _PROCESSORS.get(key)
        if proc is not None:
            return proc
        proc = FaceRuntimeProcessor(store_id=store_id, camera_id=camera_id)
        _PROCESSORS[key] = proc
        return proc


def recognize_track_face(
    frame_bgr: np.ndarray,
    person_bbox_xyxy: tuple[float, float, float, float],
    track_id: str,
    store_id: UUID,
    camera_id: UUID | None,
    ts: datetime,
    *,
    processor: FaceRuntimeProcessor | None = None,
) -> UUID | None:
    """
    Minimal hook used by the pipeline.

    NOTE: For best results in the worker, create ONE FaceRuntimeProcessor per job
    and pass it in (so state doesn't leak across jobs/cameras).
    """
    proc = processor or get_runtime_processor(store_id=store_id, camera_id=camera_id)
    res = proc.process(
        track_id=str(track_id),
        frame_bgr=frame_bgr,
        person_bbox_xyxy=person_bbox_xyxy,
        ts=ts,
    )
    return res.employee_id
