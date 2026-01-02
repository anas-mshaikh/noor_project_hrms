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

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
