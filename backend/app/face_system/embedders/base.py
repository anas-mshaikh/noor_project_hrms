"""
base.py

Abstract interface for face embedding models.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class FaceEmbedder(Protocol):
    def embed(self, face_bgr: np.ndarray) -> np.ndarray:
        """
        Compute a 512-d embedding for an aligned (or unaligned) face crop.
        Must return a float32 numpy array of shape (512,).
        """

