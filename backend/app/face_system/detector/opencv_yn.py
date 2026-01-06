"""
opencv_yn.py

OpenCV FaceDetectorYN implementation using an ONNX model.

This detector is fast and CPU-friendly. It returns face bbox + score.

Model path is configurable, default:
  <DATA_DIR>/models/facedet/facedet.onnx
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.face_system.config import FaceDetectorConfig
from app.face_system.detector.base import FaceDetection, FaceDetector


class FaceSystemModelError(RuntimeError):
    pass


@dataclass
class _DetectorState:
    # OpenCV objects are not trivially serializable; keep them in a small holder.
    detector: object


class OpenCVYNFaceDetector(FaceDetector):
    """
    OpenCV FaceDetectorYN wrapper.

    Important behavior:
    - If image height > max_detection_height, scale down for detection and rescale bboxes back.
    """

    def __init__(self, cfg: FaceDetectorConfig) -> None:
        self._cfg = cfg
        self._state: _DetectorState | None = None

    def _ensure_loaded(self) -> _DetectorState:
        if self._state is not None:
            return self._state

        import cv2  # type: ignore
        if not hasattr(cv2, "FaceDetectorYN"):
            raise FaceSystemModelError(
                "OpenCV FaceDetectorYN is missing. Install a newer OpenCV build "
                "(opencv-contrib-python recommended)."
            )

        model_path = Path(self._cfg.model_path).expanduser().resolve()
        if not model_path.exists():
            raise FaceSystemModelError(f"face detector model missing: {model_path}")

        # The input size is set per-image via setInputSize().
        detector = cv2.FaceDetectorYN.create(
            str(model_path),
            "",
            (320, 320),
            float(self._cfg.score_threshold),
            float(self._cfg.nms_threshold),
            int(self._cfg.top_k),
        )

        self._state = _DetectorState(detector=detector)
        return self._state

    def detect(self, image_bgr: np.ndarray) -> list[FaceDetection]:
        state = self._ensure_loaded()

        import cv2  # type: ignore

        img = image_bgr
        h, w = img.shape[:2]
        scale = 1.0

        # Scale down very large inputs (Frigate-style).
        if h > int(self._cfg.max_detection_height):
            scale = float(self._cfg.max_detection_height) / float(h)
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            h, w = img.shape[:2]

        # OpenCV requires updating input size for each image.
        # NOTE: type ignore because OpenCV Python stubs are incomplete.
        state.detector.setInputSize((w, h))  # type: ignore[attr-defined]

        _retval, faces = state.detector.detect(img)  # type: ignore[attr-defined]
        if faces is None:
            return []

        out: list[FaceDetection] = []
        for row in np.asarray(faces):
            # FaceDetectorYN returns: [x, y, w, h, score, ...landmarks...]
            x, y, bw, bh, score = row[:5].tolist()
            score_f = float(score)
            if score_f < float(self._cfg.score_threshold):
                continue

            x1 = float(x)
            y1 = float(y)
            x2 = float(x) + float(bw)
            y2 = float(y) + float(bh)

            if scale != 1.0:
                inv = 1.0 / scale
                x1 *= inv
                y1 *= inv
                x2 *= inv
                y2 *= inv

            # Clamp in the original image coordinate space.
            x1i = max(0, min(int(round(x1)), image_bgr.shape[1] - 1))
            y1i = max(0, min(int(round(y1)), image_bgr.shape[0] - 1))
            x2i = max(0, min(int(round(x2)), image_bgr.shape[1]))
            y2i = max(0, min(int(round(y2)), image_bgr.shape[0]))
            if x2i <= x1i or y2i <= y1i:
                continue

            out.append(
                FaceDetection(bbox_xyxy=(x1i, y1i, x2i, y2i), score=score_f)
            )

        return out

    def detect_best(self, image_bgr: np.ndarray) -> FaceDetection | None:
        faces = self.detect(image_bgr)
        if not faces:
            return None
        # Prefer largest face; break ties by score.
        return max(faces, key=lambda f: (f.area(), f.score))
