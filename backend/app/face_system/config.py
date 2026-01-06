"""
config.py

Dataclasses that define configuration for the face subsystem.

We keep config in dataclasses (not pydantic models) because:
- It's easier to share between API and worker.
- It can be instantiated from app.core.config.Settings (env-driven).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


@dataclass(frozen=True)
class FaceDetectorConfig:
    # OpenCV FaceDetectorYN ONNX model.
    model_path: Path
    score_threshold: float = 0.5
    nms_threshold: float = 0.3
    top_k: int = 5000

    # If the input is too large, scale down before detection (Frigate-style).
    max_detection_height: int = 1080


@dataclass(frozen=True)
class FaceAlignerConfig:
    # OpenCV FacemarkLBF landmark model (YAML).
    landmark_model_path: Path

    # Output aligned face size (Frigate/ArcFace style).
    output_width: int = 112
    output_height: int = 112

    # If alignment fails, allow embedding from the raw face crop.
    allow_unaligned_fallback: bool = True


@dataclass(frozen=True)
class FaceEmbedderConfig:
    # ArcFace/InsightFace embedding ONNX model path.
    # For InsightFace buffalo_l pack, this is usually w600k_r50.onnx.
    model_path: Path

    # Input size expected by ArcFace models.
    input_width: int = 112
    input_height: int = 112


@dataclass(frozen=True)
class FaceRecognizerConfig:
    # Prototype building
    trim_fraction: float = 0.15

    # Confidence mapping (sigmoid)
    sigmoid_median: float = 0.5
    sigmoid_range_width: float = 0.6
    sigmoid_slope_factor: float = 12.0

    # Any score below this is treated as "unknown".
    unknown_score: float = 0.55

    # Apply Frigate-style blur-based score reduction.
    blur_reduction_enabled: bool = True


@dataclass(frozen=True)
class FaceRuntimeConfig:
    # Cropping around the person bbox (pixels).
    pad_px: int = 12

    # Door cams often cut heads; expand bbox upward by this fraction of bbox height.
    expand_upward_frac: float = 0.35

    # Face bbox min area in pixels (in the person crop coordinate space).
    min_face_area: int = 900  # ~30x30

    # Attempt caps (Frigate-style)
    max_face_attempts: int = 12
    max_attempts_after_lock: int = 6

    # Voting / locking
    min_faces_for_lock: int = 3
    recognition_threshold: float = 0.70

    # Debug artifacts (optional)
    save_attempts: bool = False


@dataclass(frozen=True)
class FaceStorageConfig:
    """
    File-based training library.

    Directory structure (preferred):
      <face_dir>/<store_id>/<employee_id>/*.jpg

    The face_system ONLY reads from the store-scoped directory above
    (no legacy fallbacks) to keep behavior deterministic.
    """

    face_dir: Path


@dataclass(frozen=True)
class FaceSystemConfig:
    enabled: bool
    detector: FaceDetectorConfig
    aligner: FaceAlignerConfig
    embedder: FaceEmbedderConfig
    recognizer: FaceRecognizerConfig
    runtime: FaceRuntimeConfig
    storage: FaceStorageConfig

    @staticmethod
    def from_settings() -> "FaceSystemConfig":
        """
        Create FaceSystemConfig from global settings/env.
        """
        data_dir = Path(settings.data_dir).resolve()

        # Training images (file library)
        face_dir = Path(getattr(settings, "face_dir", data_dir / "faces")).resolve()

        # FaceDetectorYN requires a YuNet-style ONNX model.
        # If the model path is wrong (e.g. InsightFace det_10g.onnx), OpenCV will crash at runtime.
        facedet_model_path = Path(
            getattr(
                settings,
                "facedet_model_path",
                data_dir / "models" / "facedet" / "facedet.onnx",
            )
        ).resolve()

        landmark_model_path = Path(
            getattr(
                settings,
                "landmark_model_path",
                data_dir / "models" / "facedet" / "landmarkdet.yaml",
            )
        ).resolve()

        # Embedding model (default to InsightFace buffalo_l recognition model if present)
        arcface_model_path = Path(
            getattr(
                settings,
                "arcface_model_path",
                Path(settings.insightface_root).resolve()
                / "models"
                / settings.face_model_name
                / "w600k_r50.onnx",
            )
        ).resolve()

        return FaceSystemConfig(
            enabled=bool(getattr(settings, "face_system_enabled", True)),
            detector=FaceDetectorConfig(model_path=facedet_model_path),
            aligner=FaceAlignerConfig(
                landmark_model_path=landmark_model_path,
                allow_unaligned_fallback=bool(
                    getattr(settings, "allow_unaligned_fallback", True)
                ),
            ),
            embedder=FaceEmbedderConfig(model_path=arcface_model_path),
            recognizer=FaceRecognizerConfig(
                unknown_score=float(getattr(settings, "unknown_score", 0.55)),
            ),
            runtime=FaceRuntimeConfig(
                min_face_area=int(getattr(settings, "face_min_area", 900)),
                recognition_threshold=float(
                    getattr(settings, "recognition_threshold", 0.70)
                ),
                min_faces_for_lock=int(getattr(settings, "min_faces", 3)),
                save_attempts=bool(getattr(settings, "save_attempts", False)),
                expand_upward_frac=float(getattr(settings, "expand_upward_frac", 0.35)),
            ),
            storage=FaceStorageConfig(face_dir=face_dir),
        )
