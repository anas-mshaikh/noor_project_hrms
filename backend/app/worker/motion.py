"""
motion.py

ROI-based motion gating (cheap stage).

We use background subtraction (MOG2) inside the door ROI to decide:
- IDLE  -> no motion near door
- ACTIVE -> motion near door (run YOLO tracking)

We also keep ACTIVE for a short "hold" duration so the pipeline doesn't flicker.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import numpy as np

from app.worker.zones import Polygon, Polygons


# TODO: frigate's motion detection approach
class MotionState(str, Enum):
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"


@dataclass(frozen=True)
class MotionGateConfig:
    # If set, use this exact pixel threshold.
    threshold_area_px: int | None = None

    # Otherwise compute threshold as a fraction of ROI area (then clamp by min_area_px).
    threshold_fraction: float = 0.01
    min_area_px: int = 800

    # Require N consecutive motion frames to enter ACTIVE.
    consec_frames: int = 2

    # After motion stops, remain ACTIVE for this many seconds.
    active_hold_sec: float = 3.0

    # Background subtractor params (tune later if needed)
    mog2_history: int = 300
    mog2_var_threshold: float = 16.0


class MotionGate:
    """
    Stateful motion gate.

    Call update(frame_bgr, ts=...) per decoded frame.
    """

    def __init__(
        self,
        *,
        frame_width: int,
        frame_height: int,
        door_roi: Polygon | None,
        ignore_masks: Polygons,
        cfg: MotionGateConfig,
    ) -> None:
        self._w = int(frame_width)
        self._h = int(frame_height)
        self._cfg = cfg

        try:
            import cv2  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "opencv-python is required for motion gating. Install it via requirements.txt."
            ) from e

        # ROI mask: 255 inside ROI, 0 outside. Default ROI = full frame.
        self._roi_mask = np.ones((self._h, self._w), dtype=np.uint8) * 255
        if door_roi and len(door_roi) >= 3:
            self._roi_mask[:] = 0
            pts = np.array([[int(x), int(y)] for x, y in door_roi], dtype=np.int32)
            cv2.fillPoly(self._roi_mask, [pts], 255)

        # Subtract ignore masks from ROI.
        for poly in ignore_masks:
            if not poly or len(poly) < 3:
                continue
            pts = np.array([[int(x), int(y)] for x, y in poly], dtype=np.int32)
            cv2.fillPoly(self._roi_mask, [pts], 0)

        self.roi_area_px = int(np.count_nonzero(self._roi_mask))

        # Threshold calculation (resolution/ROI-aware)
        if cfg.threshold_area_px is not None:
            self._threshold_area_px = int(cfg.threshold_area_px)
        else:
            est = int(float(cfg.threshold_fraction) * float(self.roi_area_px))
            self._threshold_area_px = max(int(cfg.min_area_px), est)

        self._bg = cv2.createBackgroundSubtractorMOG2(
            history=int(cfg.mog2_history),
            varThreshold=float(cfg.mog2_var_threshold),
            detectShadows=False,
        )

        self.state: MotionState = MotionState.IDLE
        self._motion_streak = 0
        self._last_active_ts: datetime | None = None

        self._kernel = np.ones((3, 3), np.uint8)
        self._cv2 = cv2

    def update(self, frame_bgr: np.ndarray, *, ts: datetime) -> tuple[MotionState, int]:
        cv2 = self._cv2

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        fg = self._bg.apply(gray)  # uint8 mask

        fg = cv2.bitwise_and(fg, fg, mask=self._roi_mask)

        # Clean noise
        fg = cv2.medianBlur(fg, 5)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, self._kernel, iterations=1)

        motion_area = int(cv2.countNonZero(fg))

        # Debounce to enter ACTIVE
        if motion_area >= self._threshold_area_px:
            self._motion_streak += 1
            self._last_active_ts = ts
        else:
            self._motion_streak = 0

        if self.state == MotionState.IDLE:
            if self._motion_streak >= self._cfg.consec_frames:
                self.state = MotionState.ACTIVE
                self._last_active_ts = ts
        else:
            # ACTIVE -> IDLE only after hold time passes
            if self._last_active_ts is None:
                self._last_active_ts = ts
            quiet_sec = (ts - self._last_active_ts).total_seconds()
            if quiet_sec > float(self._cfg.active_hold_sec):
                self.state = MotionState.IDLE
                self._motion_streak = 0

        return self.state, motion_area
