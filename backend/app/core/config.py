from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Settings shared by BOTH FastAPI (API) and RQ (worker).

    Notes:
    - Env var names are derived from field names:
        database_url     -> DATABASE_URL
        yolo_model_path  -> YOLO_MODEL_PATH
        face_model_name  -> FACE_MODEL_NAME
    - Paths default to repo-relative paths (good for local dev).
    """

    # -------------------------
    # App / API
    # -------------------------
    app_name: str = "Attendance System"
    api_v1_prefix: str = "/api/v1"

    # CORS_ORIGINS is a JSON list string in .env.local, e.g.:
    #   CORS_ORIGINS='["http://localhost:3000"]'
    cors_origins: list[str] = []

    # -------------------------
    # Infrastructure
    # -------------------------
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    sqlalchemy_echo: bool = False

    # Everything uploaded/generated goes under this folder.
    # DB stores paths relative to this directory.
    data_dir: str = "./data"

    # -------------------------
    # ML model paths (offline)
    # -------------------------
    # Root folder for weights/model packs.
    # IMPORTANT: we do NOT rely on runtime downloads in the client MVP.
    model_dir: str = "./models"

    # Person detection + tracking (Ultralytics YOLO).
    # Put weights here, or override via YOLO_MODEL_PATH.
    yolo_model_path: str = "./models/yolo/yolov8n.pt"
    yolo_imgsz: int = 640
    yolo_conf: float = 0.35
    yolo_iou: float = 0.5

    # Ultralytics ships bytetrack.yaml; keep default unless you know why.
    yolo_tracker: str = "bytetrack.yaml"

    # Face recognition (InsightFace).
    # Expected directory structure:
    #   <INSIGHTFACE_ROOT>/models/<FACE_MODEL_NAME>/*
    # Example:
    #   ./models/insightface/models/buffalo_l/*.onnx
    insightface_root: str = "./models/insightface"
    face_model_name: str = "buffalo_l"
    face_det_size: int = 640  # detector input size (square)

    # -------------------------
    # Face system (Frigate-style)
    # -------------------------
    # Enable/disable the new face system (keeps old pgvector search endpoints working).
    face_system_enabled: bool = True

    # Training image library directory.
    # Default: <DATA_DIR>/faces
    face_dir: str = "./data/faces"

    # Face detector + landmark models (local files; no runtime downloads).
    # YuNet FaceDetectorYN model (OpenCV expects this format)
    facedet_model_path: str = "./models/face_det/face_detection_yunet_2023mar.onnx"
    landmark_model_path: str = "./data/models/facedet/landmarkdet.yaml"

    # ArcFace embedding ONNX model (defaults to InsightFace buffalo_l pack if present).
    arcface_model_path: str = "./models/insightface/models/buffalo_l/w600k_r50.onnx"

    # Runtime gating and thresholds
    face_min_area: int = 900
    unknown_score: float = 0.55
    recognition_threshold: float = 0.70
    min_faces: int = 3
    save_attempts: bool = False
    allow_unaligned_fallback: bool = True
    expand_upward_frac: float = 0.35

    # -------------------------
    # Attendance-first reliability (door events + tracking)
    # -------------------------
    # These are conservative guardrails to reduce false punch-ins / false exits.
    # All logic is feature-flagged so we can roll back quickly.
    enable_pending_events: bool = True
    enable_exit_pending: bool = True
    enable_recognized_stitching: bool = True

    # Two-phase door event commit: only flush weak/medium events after a track is stable.
    min_event_track_age_sec: float = 0.6
    min_event_track_hits: int = 3

    # Exit grace: when a track ends "inside", wait before emitting inferred exit.
    exit_grace_sec: float = 30.0

    # Recognized-only stitching (extremely conservative).
    stitch_gap_sec: float = 8.0
    stitch_min_lock_score: float = 0.75
    stitch_require_unique_candidate: bool = True

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
