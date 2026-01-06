"""
base.py

Abstract interface for face detectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class FaceDetection:
    """
    Face detection result in xyxy coordinates (relative to the input image).
    """

    bbox_xyxy: tuple[int, int, int, int]
    score: float

    def area(self) -> int:
        x1, y1, x2, y2 = self.bbox_xyxy
        return max(0, x2 - x1) * max(0, y2 - y1)


class FaceDetector(Protocol):
    def detect(self, image_bgr: np.ndarray) -> list[FaceDetection]:
        """
        Detect faces in a BGR image. Returns a list of detections.
        """

    def detect_best(self, image_bgr: np.ndarray) -> FaceDetection | None:
        """
        Convenience: return the largest/highest-confidence face.
        """

