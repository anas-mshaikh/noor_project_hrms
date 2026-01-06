"""
opencv_lbf.py

Frigate-style landmark-based face alignment using OpenCV FacemarkLBF.

This module implements the exact affine-warp procedure described in the task:
- Detect 68 landmarks with FacemarkLBF
- Compute eye centers (36:42 and 42:48)
- Compute rotation+scale transform so eyes match the desired positions
- Warp to (output_width, output_height)

Dependencies:
- Requires opencv-contrib-python (cv2.face.*)
- Requires a landmark model YAML (landmarkdet.yaml)
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot
from pathlib import Path

import numpy as np

from app.face_system.config import FaceAlignerConfig


class FaceSystemModelError(RuntimeError):
    pass


@dataclass
class _AlignerState:
    facemark: object


class OpenCVLBFFaceAligner:
    def __init__(self, cfg: FaceAlignerConfig) -> None:
        self._cfg = cfg
        self._state: _AlignerState | None = None

    @property
    def cfg(self) -> FaceAlignerConfig:
        return self._cfg

    def _ensure_loaded(self) -> _AlignerState:
        if self._state is not None:
            return self._state

        import cv2  # type: ignore

        # cv2.face is only available in opencv-contrib-python.
        if not hasattr(cv2, "face"):
            raise FaceSystemModelError(
                "OpenCV facemark module missing. Install opencv-contrib-python."
            )

        model_path = Path(self._cfg.landmark_model_path).expanduser().resolve()
        if not model_path.exists():
            raise FaceSystemModelError(f"landmark model missing: {model_path}")

        facemark = cv2.face.createFacemarkLBF()  # type: ignore[attr-defined]
        facemark.loadModel(str(model_path))  # type: ignore[attr-defined]

        self._state = _AlignerState(facemark=facemark)
        return self._state

    def align(self, face_bgr: np.ndarray) -> np.ndarray | None:
        """
        Returns aligned face (BGR) or None if alignment fails.
        """
        try:
            state = self._ensure_loaded()
        except FaceSystemModelError:
            # Caller can decide to fallback to unaligned crop.
            return None

        import cv2  # type: ignore

        img = face_bgr
        h, w = img.shape[:2]
        if w <= 1 or h <= 1:
            return None

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Facemark expects face rectangles. We already have a face crop, so
        # use the full crop rectangle.
        rect = (0, 0, int(w), int(h))

        ok, landmarks = state.facemark.fit(gray, np.array([rect]))  # type: ignore[attr-defined]
        if not ok or landmarks is None:
            return None

        pts = np.asarray(landmarks)[0]  # shape (68,2)
        if pts.shape[0] < 68:
            return None

        # Frigate indexing:
        # - right eye: 36..41
        # - left eye: 42..47
        right_eye = pts[36:42]
        left_eye = pts[42:48]

        right_center = right_eye.mean(axis=0)
        left_center = left_eye.mean(axis=0)

        dX = float(right_center[0] - left_center[0])
        dY = float(right_center[1] - left_center[1])
        dist = float(hypot(dX, dY))
        if dist <= 1e-6:
            return None

        # EXACT algorithm from the task description.
        angle = degrees(atan2(dY, dX)) - 180.0

        desired_left_eye_x = 0.35
        desired_right_eye_x = 1.0 - desired_left_eye_x
        desired_dist = (desired_right_eye_x - desired_left_eye_x) * float(
            self._cfg.output_width
        )
        scale = float(desired_dist / dist)

        eyes_center = (
            (float(left_center[0] + right_center[0]) * 0.5),
            (float(left_center[1] + right_center[1]) * 0.5),
        )

        M = cv2.getRotationMatrix2D(eyes_center, angle, scale)

        tX = float(self._cfg.output_width) * 0.5
        tY = float(self._cfg.output_height) * 0.35
        M[0, 2] += tX - eyes_center[0]
        M[1, 2] += tY - eyes_center[1]

        aligned = cv2.warpAffine(
            img,
            M,
            (int(self._cfg.output_width), int(self._cfg.output_height)),
            flags=cv2.INTER_CUBIC,
        )

        return aligned
