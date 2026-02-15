"""
recognizer.py

FaceRecognizer builds and maintains a "prototype embedding" per employee
for a given tenant + branch.

Frigate-style approach:
- Store many training face images per employee on disk.
- Embed each training image.
- Compute a robust prototype embedding using a trimmed mean.
- At runtime, compare query embeddings against prototypes (cosine similarity).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from threading import Lock, Thread
from uuid import UUID

import numpy as np

from app.face_system.aligners.opencv_lbf import OpenCVLBFFaceAligner
from app.face_system.config import (
    FaceAlignerConfig,
    FaceDetectorConfig,
    FaceEmbedderConfig,
    FaceRecognizerConfig,
)
from app.face_system.detector.opencv_yn import OpenCVYNFaceDetector
from app.face_system.embedders.insightface_arcface import ONNXArcFaceEmbedder
from app.face_system.storage import FaceLibraryStorage
from app.face_system.utils import (
    blur_confidence_reduction,
    blur_score_laplacian_var,
    cosine_similarity,
    l2_normalize,
    sigmoid_confidence,
    trimmed_mean,
)


class FaceSystemError(RuntimeError):
    """
    User-facing error class for API endpoints.
    """


@dataclass(frozen=True)
class PrototypeBuildStats:
    built_at: datetime
    employees: int
    images: int


@dataclass(frozen=True)
class FaceMatch:
    employee_id: UUID
    cosine_similarity: float
    confidence: float


@dataclass(frozen=True)
class FaceRecognizeResult:
    """
    Result of classifying a query embedding.
    """

    employee_id: UUID | None  # None => unknown
    confidence: float
    cosine_similarity: float | None
    top_k: list[FaceMatch]


def _iter_branch_employee_dirs(
    face_dir: Path, *, tenant_id: UUID, branch_id: UUID
) -> list[tuple[UUID, Path]]:
    """
    Scan <face_dir>/<tenant_id>/<branch_id>/<employee_id>/ folders.
    """
    branch_dir = face_dir / str(tenant_id) / str(branch_id)
    if not branch_dir.exists():
        return []

    out: list[tuple[UUID, Path]] = []
    for child in branch_dir.iterdir():
        if not child.is_dir():
            continue
        try:
            emp_id = UUID(child.name)
        except Exception:
            continue
        out.append((emp_id, child))
    return out


def _iter_image_files(dir_path: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(dir_path.glob("*")):
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            out.append(p)
    return out


class FaceRecognizer:
    """
    Branch-scoped prototype recognizer.

    Threading model:
    - trigger_rebuild_async() spawns a background build thread
    - poll() is called opportunistically from API/pipeline to collect build results
    - ensure_built(block=True) can block (useful in worker pipeline)
    """

    def __init__(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        detector_cfg: FaceDetectorConfig,
        aligner_cfg: FaceAlignerConfig,
        embedder_cfg: FaceEmbedderConfig,
        recognizer_cfg: FaceRecognizerConfig,
        storage: FaceLibraryStorage,
    ) -> None:
        self.tenant_id = tenant_id
        self.branch_id = branch_id
        self.cfg = recognizer_cfg
        self.storage = storage

        # Heavy model objects (lazy-load inside wrappers).
        self._detector = OpenCVYNFaceDetector(detector_cfg)
        self._aligner = OpenCVLBFFaceAligner(aligner_cfg)
        self._embedder = ONNXArcFaceEmbedder(embedder_cfg)

        self._lock = Lock()
        self._prototypes: dict[UUID, np.ndarray] = {}
        self._stats: PrototypeBuildStats | None = None

        self._build_thread: Thread | None = None
        self._build_results: Queue[tuple[dict[UUID, np.ndarray], PrototypeBuildStats]] = Queue()

    # -------------------------
    # Public API
    # -------------------------
    def clear(self) -> None:
        """
        Clear prototypes. Next recognition will rebuild (lazy).
        """
        with self._lock:
            self._prototypes = {}
            self._stats = None

    def stats(self) -> PrototypeBuildStats | None:
        with self._lock:
            return self._stats

    def prototypes_ready(self) -> bool:
        with self._lock:
            return bool(self._prototypes)

    def trigger_rebuild_async(self) -> None:
        """
        Start async build, if not already running.
        """
        with self._lock:
            if self._build_thread is not None and self._build_thread.is_alive():
                return

            t = Thread(target=self._build_worker, daemon=True)
            self._build_thread = t
            t.start()

    def poll(self) -> None:
        """
        Apply finished build results (non-blocking).
        """
        try:
            prototypes, stats = self._build_results.get_nowait()
        except Exception:
            return

        with self._lock:
            self._prototypes = prototypes
            self._stats = stats

    def ensure_built(self, *, block: bool = True, timeout_sec: float = 30.0) -> None:
        """
        Ensure prototypes exist.

        - In API: block=False is fine (respond "building" if needed).
        - In worker pipeline: block=True is recommended (build once per job).
        """
        if self.prototypes_ready():
            return

        self.trigger_rebuild_async()

        if not block:
            return

        # Block until build thread finishes or timeout is reached.
        import time

        deadline = time.time() + float(timeout_sec)
        while time.time() < deadline:
            self.poll()
            if self.prototypes_ready():
                return
            time.sleep(0.05)

        # Still not ready: give a clear error to the caller.
        raise FaceSystemError("no prototypes built (still building or build failed)")

    def recognize_embedding(
        self,
        embedding: np.ndarray,
        *,
        blur_score: float | None = None,
        top_k: int = 5,
    ) -> FaceRecognizeResult:
        """
        Compare query embedding against employee prototypes.
        """
        self.poll()
        self.ensure_built(block=False)

        with self._lock:
            prototypes = dict(self._prototypes)

        if not prototypes:
            raise FaceSystemError("no prototypes built")

        query = l2_normalize(embedding.astype(np.float32))

        matches: list[FaceMatch] = []
        for emp_id, proto in prototypes.items():
            sim = cosine_similarity(query, proto)
            conf = sigmoid_confidence(
                sim,
                median=self.cfg.sigmoid_median,
                range_width=self.cfg.sigmoid_range_width,
                slope_factor=self.cfg.sigmoid_slope_factor,
            )

            # Optional blur-based reduction (Frigate-style).
            if self.cfg.blur_reduction_enabled and blur_score is not None:
                conf = max(0.0, float(conf) - blur_confidence_reduction(float(blur_score)))

            matches.append(
                FaceMatch(
                    employee_id=emp_id,
                    cosine_similarity=float(sim),
                    confidence=float(conf),
                )
            )

        # Sort best-first by confidence, then similarity.
        matches.sort(key=lambda m: (m.confidence, m.cosine_similarity), reverse=True)

        top = matches[: max(1, min(int(top_k), 50))]
        best = top[0] if top else None

        if best is None or best.confidence < float(self.cfg.unknown_score):
            return FaceRecognizeResult(
                employee_id=None,
                confidence=float(best.confidence if best else 0.0),
                cosine_similarity=float(best.cosine_similarity if best else 0.0)
                if best
                else None,
                top_k=top,
            )

        return FaceRecognizeResult(
            employee_id=best.employee_id,
            confidence=float(best.confidence),
            cosine_similarity=float(best.cosine_similarity),
            top_k=top,
        )

    def recognize_image(
        self, image_bgr: np.ndarray, *, top_k: int = 5
    ) -> FaceRecognizeResult:
        """
        Convenience helper for API endpoints:
        - detect best face
        - align (optional)
        - embed
        - classify
        """
        face_det = self._detector.detect_best(image_bgr)
        if face_det is None:
            raise FaceSystemError("no face detected")

        x1, y1, x2, y2 = face_det.bbox_xyxy
        face_crop = image_bgr[y1:y2, x1:x2].copy()
        if face_crop.size == 0:
            raise FaceSystemError("invalid face crop")

        aligned = self._aligner.align(face_crop)
        if aligned is None:
            if not bool(self._aligner.cfg.allow_unaligned_fallback):
                raise FaceSystemError("alignment failed")
            aligned = face_crop

        emb = self._embedder.embed(aligned)
        blur = blur_score_laplacian_var(face_crop)

        return self.recognize_embedding(emb, blur_score=blur, top_k=top_k)

    # -------------------------
    # Internal build worker
    # -------------------------
    def _build_worker(self) -> None:
        """
        Background task:
        - read training images from disk
        - align + embed
        - compute trimmed mean per employee
        """
        try:
            prototypes, stats = self._build_prototypes()
            self._build_results.put((prototypes, stats))
        except Exception:
            # Swallow exceptions: callers will see "no prototypes built".
            # For production, you can add structured logging here.
            return

    def _build_prototypes(self) -> tuple[dict[UUID, np.ndarray], PrototypeBuildStats]:
        import cv2  # type: ignore

        face_dir = self.storage.face_dir
        employee_dirs = _iter_branch_employee_dirs(
            face_dir, tenant_id=self.tenant_id, branch_id=self.branch_id
        )

        total_images = 0
        prototypes: dict[UUID, np.ndarray] = {}

        for emp_id, emp_dir in employee_dirs:
            image_paths = _iter_image_files(emp_dir)
            if not image_paths:
                continue

            embs: list[np.ndarray] = []
            for p in image_paths:
                img = cv2.imread(str(p))
                if img is None:
                    continue

                # Training images are expected to be face crops (registration stores cropped faces),
                # so we skip running face detection again.
                aligned = self._aligner.align(img)
                if aligned is None:
                    if not bool(self._aligner.cfg.allow_unaligned_fallback):
                        continue
                    aligned = img

                try:
                    emb = self._embedder.embed(aligned)
                except Exception:
                    continue

                embs.append(emb)

            total_images += len(embs)
            if not embs:
                continue

            proto = trimmed_mean(embs, trim_fraction=float(self.cfg.trim_fraction))
            prototypes[emp_id] = l2_normalize(proto)

        stats = PrototypeBuildStats(
            built_at=datetime.now(timezone.utc),
            employees=len(prototypes),
            images=int(total_images),
        )
        return prototypes, stats
