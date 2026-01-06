"""
utils.py

Small, testable image/math helpers.
Keep these pure where possible so unit tests don't require models.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from pathlib import Path
from typing import Hashable, Iterable, TypeVar

import numpy as np


@dataclass(frozen=True)
class BBox:
    """
    Pixel bbox in xyxy form.
    """

    x1: int
    y1: int
    x2: int
    y2: int

    def clamp(self, *, w: int, h: int) -> "BBox":
        x1 = max(0, min(int(self.x1), w - 1))
        y1 = max(0, min(int(self.y1), h - 1))
        x2 = max(0, min(int(self.x2), w))
        y2 = max(0, min(int(self.y2), h))
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        return BBox(x1=x1, y1=y1, x2=x2, y2=y2)

    def width(self) -> int:
        return max(0, int(self.x2) - int(self.x1))

    def height(self) -> int:
        return max(0, int(self.y2) - int(self.y1))

    def area(self) -> int:
        return self.width() * self.height()

    def as_xyxy(self) -> tuple[int, int, int, int]:
        return (int(self.x1), int(self.y1), int(self.x2), int(self.y2))


def expand_upward_bbox(
    bbox_xyxy: tuple[float, float, float, float],
    *,
    frame_w: int,
    frame_h: int,
    pad_px: int,
    expand_upward_frac: float,
) -> BBox:
    """
    Expand a person bbox upward to include the head region (door-cam friendly).

    This is a pure math helper used by the runtime processor.
    """
    x1, y1, x2, y2 = [float(v) for v in bbox_xyxy]
    bh = max(1.0, y2 - y1)

    # Expand upward by a fraction of bbox height.
    y1 = y1 - (expand_upward_frac * bh)

    x1 -= float(pad_px)
    y1 -= float(pad_px)
    x2 += float(pad_px)
    y2 += float(pad_px)

    return BBox(int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))).clamp(
        w=frame_w, h=frame_h
    )


def blur_score_laplacian_var(image_bgr: np.ndarray) -> float:
    """
    Variance of Laplacian (higher => sharper).
    """
    # Lazy import so unit tests that don't touch blur can still run without OpenCV.
    import cv2  # type: ignore

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def l2_normalize(vec: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    denom = float(np.linalg.norm(vec) + eps)
    return (vec / denom).astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine similarity for vectors (safe even if not normalized).
    """
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    return float(
        np.dot(a, b) / ((np.linalg.norm(a) + 1e-9) * (np.linalg.norm(b) + 1e-9))
    )


def sigmoid_confidence(
    cos_sim: float,
    *,
    median: float,
    range_width: float,
    slope_factor: float,
) -> float:
    """
    Frigate-style mapping from cosine similarity to a [0..1] confidence score.
    """
    # Prevent divide-by-zero.
    rw = max(1e-6, float(range_width))
    slope = float(slope_factor) / rw
    x = float(cos_sim) - float(median)
    return float(1.0 / (1.0 + exp(-slope * x)))


def blur_confidence_reduction(blur: float) -> float:
    """
    Frigate-style blur penalty mapping.
    """
    if blur < 120:
        return 0.06
    if blur < 160:
        return 0.04
    if blur < 200:
        return 0.02
    if blur < 250:
        return 0.01
    return 0.0


def safe_basename(name: str) -> str:
    """
    Prevent path traversal for delete APIs.
    """
    return Path(name).name


def trimmed_mean(
    vectors: Iterable[np.ndarray],
    *,
    trim_fraction: float,
) -> np.ndarray:
    """
    Coordinate-wise trimmed mean for a list of equal-shaped vectors.

    We implement this manually so we don't need scipy.
    """
    arr = np.stack([v.astype(np.float32) for v in vectors], axis=0)
    n = int(arr.shape[0])
    if n == 0:
        raise ValueError("trimmed_mean requires at least one vector")
    if n == 1:
        return arr[0]

    trim = float(trim_fraction)
    trim = max(0.0, min(trim, 0.49))
    k = int(n * trim)
    if (2 * k) >= n:
        k = max(0, (n - 1) // 2)

    # Sort along the sample axis (0), trim extremes, average remaining.
    sorted_arr = np.sort(arr, axis=0)
    kept = sorted_arr[k : n - k, :]
    return np.mean(kept, axis=0).astype(np.float32)


TId = TypeVar("TId", bound=Hashable)


def vote_weighted_identity(
    attempts: Iterable[tuple[TId | None, float, int]],
    *,
    unknown_score: float,
    min_faces: int,
    threshold: float,
) -> tuple[TId, float] | None:
    """
    Frigate-style weighted voting (pure helper).

    Inputs:
    - attempts: iterable of (employee_id, confidence, face_area)
      - employee_id is None => "unknown"
      - confidence is a 0..1 score (after any blur penalty)
      - face_area is used as a weight proxy (larger face => more reliable)

    Algorithm (matches the spec):
    - ignore unknown
    - ignore confidence < unknown_score
    - pick the employee with the highest COUNT of valid attempts
    - if tie in counts => return None
    - require winner count >= min_faces
    - compute a weighted-average confidence for the winner:
        weight = min(face_area, 4000) * max(0, (confidence - unknown_score) * 10)
    - require weighted score >= threshold
    """
    unknown_score_f = float(unknown_score)
    min_faces_i = int(min_faces)
    threshold_f = float(threshold)

    valid: list[tuple[TId, float, int]] = []
    for emp_id, conf, area in attempts:
        if emp_id is None:
            continue
        conf_f = float(conf)
        if conf_f < unknown_score_f:
            continue
        valid.append((emp_id, conf_f, int(area)))

    if not valid:
        return None

    # Count votes per employee.
    counts: dict[TId, int] = {}
    for emp_id, _conf, _area in valid:
        counts[emp_id] = counts.get(emp_id, 0) + 1

    top_count = max(counts.values())
    winners = [emp_id for emp_id, c in counts.items() if c == top_count]
    if len(winners) != 1:
        return None
    winner = winners[0]
    if top_count < min_faces_i:
        return None

    # Weighted average score for the winner.
    weights: list[float] = []
    scores: list[float] = []
    for emp_id, conf, area in valid:
        if emp_id != winner:
            continue
        w = float(min(int(area), 4000))
        w *= max(0.0, (float(conf) - unknown_score_f) * 10.0)
        weights.append(w)
        scores.append(float(conf))

    wsum = float(sum(weights))
    if wsum <= 1e-9:
        score = float(sum(scores) / max(1, len(scores)))
    else:
        score = float(sum(w * s for w, s in zip(weights, scores)) / wsum)

    if score < threshold_f:
        return None
    return winner, float(score)
