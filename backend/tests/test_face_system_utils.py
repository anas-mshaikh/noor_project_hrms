import sys
import unittest
from pathlib import Path
from uuid import UUID

import numpy as np

# Ensure `import app.*` works when tests are run from repo root.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.face_system.utils import (  # noqa: E402
    cosine_similarity,
    expand_upward_bbox,
    sigmoid_confidence,
    trimmed_mean,
    vote_weighted_identity,
)


class TestFaceSystemUtils(unittest.TestCase):
    def test_cosine_similarity_identical_is_one(self) -> None:
        v = np.asarray([1.0, 2.0, 3.0], dtype=np.float32)
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0, places=6)

    def test_cosine_similarity_orthogonal_is_zero(self) -> None:
        a = np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
        b = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
        self.assertAlmostEqual(cosine_similarity(a, b), 0.0, places=6)

    def test_sigmoid_confidence_is_half_at_median(self) -> None:
        self.assertAlmostEqual(
            sigmoid_confidence(0.5, median=0.5, range_width=0.6, slope_factor=12.0),
            0.5,
            places=6,
        )

    def test_trimmed_mean_with_outlier(self) -> None:
        v0 = np.asarray([0.0, 0.0], dtype=np.float32)
        v1 = np.asarray([10.0, 10.0], dtype=np.float32)
        v2 = np.asarray([1000.0, 1000.0], dtype=np.float32)

        # With 3 samples, trim_fraction ~0.34 trims 1 from each side -> keeps only v1.
        out = trimmed_mean([v0, v1, v2], trim_fraction=0.34)
        self.assertTrue(np.allclose(out, v1, atol=1e-6))

    def test_vote_weighted_identity_tie_returns_none(self) -> None:
        a = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        b = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

        # Two votes each => tie.
        attempts = [
            (a, 0.8, 3000),
            (a, 0.8, 3000),
            (b, 0.8, 3000),
            (b, 0.8, 3000),
        ]
        res = vote_weighted_identity(
            attempts, unknown_score=0.55, min_faces=3, threshold=0.7
        )
        self.assertIsNone(res)

    def test_vote_weighted_identity_requires_min_faces(self) -> None:
        a = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

        # Only 2 valid faces but min_faces=3.
        attempts = [(a, 0.9, 3000), (a, 0.9, 3000)]
        res = vote_weighted_identity(
            attempts, unknown_score=0.55, min_faces=3, threshold=0.7
        )
        self.assertIsNone(res)

    def test_vote_weighted_identity_locks_winner(self) -> None:
        a = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        attempts = [
            (None, 0.99, 4000),  # ignored unknown
            (a, 0.8, 2500),
            (a, 0.8, 3000),
            (a, 0.8, 3500),
        ]
        res = vote_weighted_identity(
            attempts, unknown_score=0.55, min_faces=3, threshold=0.7
        )
        self.assertIsNotNone(res)
        emp_id, score = res  # type: ignore[misc]
        self.assertEqual(emp_id, a)
        self.assertGreaterEqual(float(score), 0.7)

    def test_expand_upward_bbox_clamps_to_frame(self) -> None:
        bbox = (10.0, 5.0, 20.0, 25.0)
        out = expand_upward_bbox(
            bbox,
            frame_w=100,
            frame_h=100,
            pad_px=12,
            expand_upward_frac=0.35,
        )
        x1, y1, x2, y2 = out.as_xyxy()
        self.assertGreaterEqual(x1, 0)
        self.assertGreaterEqual(y1, 0)  # should clamp after expansion
        self.assertLessEqual(x2, 100)
        self.assertLessEqual(y2, 100)


if __name__ == "__main__":
    unittest.main()

