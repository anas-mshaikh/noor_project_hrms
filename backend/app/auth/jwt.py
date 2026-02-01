from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings


def create_access_token(*, subject: str, expires_in: timedelta | None = None, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    ttl = expires_in or timedelta(minutes=settings.auth_access_token_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.auth_jwt_secret_key, algorithm=settings.auth_jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.auth_jwt_secret_key,
        algorithms=[settings.auth_jwt_algorithm],
        options={"require": ["exp", "iat", "sub"]},
    )


def create_refresh_token() -> str:
    # Random secret; stored hashed in DB. URL-safe for clients.
    return secrets.token_urlsafe(48)

