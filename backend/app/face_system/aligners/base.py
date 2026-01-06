"""
base.py

Abstract interface for face alignment.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class FaceAligner(Protocol):
    def align(self, face_bgr: np.ndarray) -> np.ndarray | None:
        """
        Align a face crop and return the aligned BGR image.
        Return None when alignment fails.
        """

