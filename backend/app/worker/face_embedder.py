"""
face_embedder.py

One wrapper around InsightFace that BOTH API and worker can use.

What we do here:
- Detect faces in an image (BGR numpy array)
- Produce a 512-d embedding (matches EmployeeFace.embedding Vector(512))
- Compute a simple quality score:
    - size (bigger face bbox is better)
    - blur (Laplacian variance)
"""

from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings


# TODO: Research on Frigate's face embedding approach
class FaceEmbedderError(RuntimeError):
    pass


@dataclass(frozen=True)
class FaceEmbeddingResult:
    # 512-d embedding (float32 -> python floats)
    embedding: list[float]

    # Face bbox in the INPUT image coordinate space
    bbox_xyxy: tuple[int, int, int, int]

    # Face crop for saving snapshots / debugging
    face_crop_bgr: np.ndarray

    # Raw blur metric (higher is sharper)
    blur_score: float

    # Simple normalized 0..1 quality score (size + blur)
    quality_score: float

    # Helpful for debugging / audits
    model_version: str


def _import_cv2():
    try:
        import cv2  # type: ignore
    except Exception as e:
        raise FaceEmbedderError(
            "opencv-python is required for face embedding. Install it via requirements.txt."
        ) from e
    return cv2


def read_image_bgr(path: Path) -> np.ndarray:
    """
    Read an image from disk into BGR numpy array (OpenCV convention).
    """
    cv2 = _import_cv2()
    img = cv2.imread(str(path))
    if img is None:
        raise FaceEmbedderError(f"Could not read image: {path}")
    return img


class FaceEmbedder:
    """
    Thin wrapper around insightface.app.FaceAnalysis.

    We keep it small so it's easy to swap models later.
    """

    def __init__(self, *, app: Any, model_version: str) -> None:
        self._app = app
        self.model_version = model_version

    def detect_and_embed(self, image_bgr: np.ndarray) -> list[FaceEmbeddingResult]:
        """
        Returns embeddings for ALL faces found in the image.
        """
        cv2 = _import_cv2()

        faces = self._app.get(image_bgr) or []
        if not faces:
            return []

        h, w = image_bgr.shape[:2]
        out: list[FaceEmbeddingResult] = []

        for f in faces:
            bbox = getattr(f, "bbox", None)
            emb = getattr(f, "embedding", None)
            if bbox is None or emb is None:
                continue

            x1, y1, x2, y2 = [int(round(float(v))) for v in bbox.tolist()]

            # Clamp bbox to image
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))
            if x2 <= x1 or y2 <= y1:
                continue

            crop = image_bgr[y1:y2, x1:x2].copy()

            # Blur score (cheap and good enough for gating)
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())

            # Quality score (0..1) - tune later
            face_w = float(x2 - x1)
            face_h = float(y2 - y1)
            area = face_w * face_h

            # size_score reaches 1 around ~80x80 faces
            size_score = min(1.0, area / float(80.0 * 80.0))

            # blur_score reaches 1 around ~150 variance (rough heuristic)
            blur_score = min(1.0, blur / 150.0)

            quality = float(size_score * blur_score)

            out.append(
                FaceEmbeddingResult(
                    embedding=np.asarray(emb, dtype=np.float32).tolist(),
                    bbox_xyxy=(x1, y1, x2, y2),
                    face_crop_bgr=crop,
                    blur_score=blur,
                    quality_score=quality,
                    model_version=self.model_version,
                )
            )

        return out

    def embed_best_face(self, image_bgr: np.ndarray) -> FaceEmbeddingResult | None:
        """
        Convenience: pick the largest face (best chance of correct recognition).
        """
        faces = self.detect_and_embed(image_bgr)
        if not faces:
            return None

        def area(face: FaceEmbeddingResult) -> int:
            x1, y1, x2, y2 = face.bbox_xyxy
            return max(0, x2 - x1) * max(0, y2 - y1)

        return max(faces, key=area)

    def embed_single_face(self, image_bgr: np.ndarray) -> FaceEmbeddingResult:
        """
        Strict mode used for enrollment:
        - 0 faces => error
        - >1 faces => error (avoid enrolling the wrong person)
        """
        faces = self.detect_and_embed(image_bgr)
        if not faces:
            raise FaceEmbedderError("No face detected in image")
        if len(faces) > 1:
            raise FaceEmbedderError(
                f"Multiple faces detected ({len(faces)}). Upload a single-person face image."
            )
        return faces[0]


@lru_cache
def get_face_embedder() -> FaceEmbedder:
    """
    Singleton loader (models are heavy; load once per process).
    """
    try:
        from insightface.app import FaceAnalysis  # type: ignore
    except Exception as e:
        raise FaceEmbedderError(
            "insightface is required for face embeddings. Install it via requirements.txt."
        ) from e

    root = Path(settings.insightface_root).expanduser().resolve()
    model_dir = root / "models" / settings.face_model_name
    if not model_dir.exists():
        raise FaceEmbedderError(
            f"InsightFace model pack not found at: {model_dir}\n"
            "Download the model pack (e.g. buffalo_l) and place it under:\n"
            f"  {root}/models/{settings.face_model_name}/"
        )

    # Force CPU provider for maximum compatibility (you can tune later).
    app = FaceAnalysis(
        name=settings.face_model_name,
        root=str(root),
        providers=["CPUExecutionProvider"],
    )

    det = int(settings.face_det_size)
    app.prepare(ctx_id=0, det_size=(det, det))

    return FaceEmbedder(
        app=app, model_version=f"insightface:{settings.face_model_name}"
    )
