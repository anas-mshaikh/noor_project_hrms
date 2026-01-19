from __future__ import annotations

"""
Firebase Admin SDK helpers (singleton pattern).

Why this exists:
- Multiple parts of the backend need Firebase (Firestore sync, Auth provisioning).
- The Admin SDK must be initialized once per process.
- Credentials may be provided as a file path or a base64 JSON blob.

We keep the API intentionally small:
- get_firestore_client()
- get_auth_module() (returns firebase_admin.auth)
"""

import base64
import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def _load_service_account_info() -> dict[str, Any]:
    """
    Load service account JSON from env.

    Supported env vars (see Settings):
    - FIREBASE_SERVICE_ACCOUNT_JSON_BASE64 (preferred)
    - FIREBASE_SERVICE_ACCOUNT_JSON (legacy name, still supported)
    - FIREBASE_SERVICE_ACCOUNT_PATH

    The JSON env vars must be base64-encoded to avoid issues with multiline keys.
    """

    raw_b64 = None
    if settings.firebase_service_account_json_base64:
        raw_b64 = settings.firebase_service_account_json_base64.strip()
    elif settings.firebase_service_account_json:
        raw_b64 = settings.firebase_service_account_json.strip()

    if raw_b64:
        decoded = base64.b64decode(raw_b64)
        return json.loads(decoded)

    if settings.firebase_service_account_path:
        with open(settings.firebase_service_account_path, "r", encoding="utf-8") as f:
            return json.load(f)

    raise RuntimeError(
        "Firebase service account missing. Set FIREBASE_SERVICE_ACCOUNT_JSON_BASE64 "
        "(preferred) or FIREBASE_SERVICE_ACCOUNT_PATH."
    )


def _ensure_initialized():
    """
    Initialize firebase_admin exactly once.

    Notes:
    - firebase_admin keeps global state in firebase_admin._apps.
    - We rely on that to be our process-wide singleton.
    """
    try:
        import firebase_admin  # type: ignore
        from firebase_admin import credentials  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"firebase-admin is required for Firebase features. ({e})") from e

    if firebase_admin._apps:  # type: ignore[attr-defined]
        return

    info = _load_service_account_info()
    cred = credentials.Certificate(info)

    # Optionally pin project id if provided; the certificate usually contains it.
    options: dict[str, Any] = {}
    if settings.firebase_project_id:
        options["projectId"] = settings.firebase_project_id

    firebase_admin.initialize_app(cred, options or None)
    logger.info("firebase admin initialized project_id=%s", settings.firebase_project_id)


def get_firestore_client():
    """
    Return a Firestore client (requires Firebase Admin SDK).
    """
    _ensure_initialized()
    from firebase_admin import firestore  # type: ignore

    return firestore.client()


def get_auth_module():
    """
    Return the firebase_admin.auth module.

    The Admin SDK exposes Auth operations as functions on a module, not an object.
    """
    _ensure_initialized()
    from firebase_admin import auth  # type: ignore

    return auth

