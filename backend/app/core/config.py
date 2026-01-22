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
    # HR module (Phase 1/2)
    # -------------------------
    # Phase 1 stores resumes + parsed artifacts under:
    #   <DATA_DIR>/hr/resumes/<opening_id>/<resume_id>/...
    #
    # Phase 2 stores embeddings in Postgres (pgvector) using BGE-M3 (1024-d).
    hr_embeddings_enabled: bool = True
    hr_embed_model_name: str = "BAAI/bge-m3"
    # IMPORTANT: must match the DB column type `vector(<dim>)` in `hr_resume_views.embedding`.
    # If you switch to a model with a different embedding size, you must:
    # 1) create a migration to change the vector column dimension, and
    # 2) update this setting.
    hr_embed_dim: int = 1024
    # Cache directory for HuggingFace model downloads.
    # In Docker, mount `./backend/models` to persist caches.
    hr_embed_cache_dir: str = "./models/text_embeddings"
    hr_embed_device: str = "cpu"
    # BGE-M3 supports very long contexts; keep configurable because higher values
    # cost more CPU/RAM. If the library/model doesn't support it, we fall back.
    hr_embed_max_seq_length: int = 8192
    # Safety truncation for extremely long resumes (char-based, cheap).
    hr_embed_max_chars: int = 12000
    # Minimum chars required for derived "skills"/"experience" views.
    hr_view_min_chars: int = 120
    # Debug-only semantic search endpoint for HR (MVP retrieval).
    hr_search_debug_enabled: bool = False

    # -------------------------
    # HR module (Phase 3): Screening runs (retrieve + rerank)
    # -------------------------
    # Phase 3 introduces an async "ScreeningRun" pipeline:
    # 1) retrieve Top-K candidates using pgvector embeddings (Phase 2),
    # 2) rerank the candidate pool using a BGE reranker model, and
    # 3) store ranked results for later paging/export.
    #
    # All of this remains local: Redis/RQ for async, Postgres for storage.
    hr_rerank_enabled: bool = True
    hr_reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    # Reranker batch size is a tradeoff: higher is faster but uses more RAM.
    hr_reranker_batch_size: int = 32
    # Safety truncation for reranker inputs (char-based).
    hr_reranker_max_chars: int = 12000
    # Default ScreeningRun config (used when API caller doesn't provide overrides).
    hr_screening_default_view_types: list[str] = ["skills", "experience", "full"]
    hr_screening_default_k_per_view: int = 200
    hr_screening_default_pool_size: int = 400
    hr_screening_default_top_n: int = 200
    # Job timeout for ScreeningRun jobs (reranking can be slow on CPU).
    hr_screening_job_timeout_sec: int = 60 * 60  # 60 minutes
    # How often the worker should persist progress updates (in processed docs).
    hr_screening_progress_update_every: int = 10

    # -------------------------
    # HR module (Phase 4): Explanations (Gemini)
    # -------------------------
    # Phase 4 adds post-ranking explanations for top ScreeningRun candidates.
    #
    # Key design goals:
    # - Run asynchronously via RQ so ScreeningRuns are not blocked.
    # - Store ONLY structured JSON outputs (no raw resume text persisted to DB).
    # - Keep config minimal and environment-driven.
    #
    # Operational note:
    # - If GEMINI_API_KEY is missing/empty, the backend will skip auto-enqueueing
    #   explanation jobs and manual endpoints will return a clear error.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash-lite-001"
    gemini_timeout_sec: int = 60
    # Hard cap for "explain top N" to control spend and latency during MVP.
    gemini_max_top_n: int = 20

    # -------------------------
    # Phase 2: Admin imports (Excel)
    # -------------------------
    # Raw uploaded XLSX files are stored here (dataset_id is part of the filename).
    # Postgres remains the source of truth; these raw files are for audit/re-import.
    upload_dir: str = "./data/imports"
    # If a dataset upload previously FAILED, allow re-uploading the same file (same checksum)
    # to re-validate using the current parser code, reusing the same dataset_id.
    # This preserves idempotency while making development/debugging much easier.
    imports_revalidate_failed_on_reupload: bool = True

    # Firebase credentials (used by mobile sync).
    firebase_service_account_path: str | None = None
    firebase_service_account_json: str | None = None
    # Alias for clarity: this should contain BASE64-encoded JSON.
    # We keep `firebase_service_account_json` for backwards compatibility in dev.
    firebase_service_account_json_base64: str | None = None
    firebase_project_id: str | None = None

    # -------------------------
    # Phase 3: Mobile sync
    # -------------------------
    mobile_sync_enabled: bool = False
    mobile_sync_dry_run: bool = False
    mobile_sync_admin_enabled: bool = False
    mobile_sync_admin_token: str | None = None
    mobile_sync_leaderboard_limit: int = 50

    # -------------------------
    # Mobile app login bootstrap mapping
    # -------------------------
    # Development-only guard for admin endpoints that provision/revoke mobile accounts.
    # If false, we return 404 to avoid accidentally exposing these endpoints.
    admin_mode: bool = False
    # If true, do NOT call Firebase (Auth/Firestore). We will only log payloads.
    # Useful for local development where Firebase credentials are not available.
    mobile_mapping_dry_run: bool = False

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

    # -------------------------
    # Snapshot quality-of-life (debugging / auditing)
    # -------------------------
    # Save one "last seen" full-frame snapshot per track (overwritten as the track moves).
    # This is used as a fallback snapshot for inferred exits (track_ended_inside),
    # which otherwise have no frame to capture at finalization time.
    #
    # Env vars:
    #   SAVE_LAST_SEEN_SNAPSHOTS=true|false
    #   LAST_SEEN_SNAPSHOT_INTERVAL_SEC=2.0
    #   ATTACH_LAST_SEEN_SNAPSHOT_TO_INFERRED_EXIT=true|false
    save_last_seen_snapshots: bool = True
    last_seen_snapshot_interval_sec: float = 2.0
    attach_last_seen_snapshot_to_inferred_exit: bool = True

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
