from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.auth import repo
from app.auth.jwt import create_access_token, create_refresh_token
from app.auth.passwords import verify_password
from app.auth.scope import resolve_scope, roles_for_scope
from app.core.config import settings
from app.core.errors import AppError
from app.shared.types import AuthContext


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


def _hash_refresh_token(raw_refresh_token: str) -> str:
    raw = (raw_refresh_token + settings.auth_refresh_token_pepper).encode()
    return hashlib.sha256(raw).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _refresh_expires_at(now: datetime) -> datetime:
    return now + timedelta(days=settings.auth_refresh_token_ttl_days)


class AuthService:
    def login(
        self,
        db: Session,
        *,
        email: str,
        password: str,
        headers: dict[str, str],
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[TokenPair, AuthContext]:
        user = repo.get_user_by_email(db, email=email)
        if user is None or user.password_hash is None:
            raise AppError(code="invalid_credentials", message="Invalid credentials", status_code=401)
        if user.status != "ACTIVE" or user.deleted_at is not None:
            raise AppError(code="unauthorized", message="User is disabled", status_code=401)
        if not verify_password(user.password_hash, password):
            raise AppError(code="invalid_credentials", message="Invalid credentials", status_code=401)

        now = _now()
        user.last_login_at = now

        refresh = create_refresh_token()
        repo.insert_refresh_token(
            db,
            user_id=user.id,
            token_hash=_hash_refresh_token(refresh),
            expires_at=_refresh_expires_at(now),
            ip=ip,
            user_agent=user_agent,
        )
        db.commit()

        access = create_access_token(subject=str(user.id))
        scope = resolve_scope(db, user_id=user.id, headers=headers)
        assignments = repo.list_role_assignments(db, user_id=user.id)
        roles = roles_for_scope(assignments=assignments, scope=scope)

        ctx = AuthContext(user_id=user.id, email=user.email, status=user.status, roles=roles, scope=scope)
        return TokenPair(access_token=access, refresh_token=refresh), ctx

    def refresh(
        self,
        db: Session,
        *,
        refresh_token: str,
        headers: dict[str, str],
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[TokenPair, AuthContext]:
        now = _now()
        token_hash = _hash_refresh_token(refresh_token)
        rt = repo.get_refresh_token_by_hash(db, token_hash=token_hash)
        if rt is None:
            raise AppError(code="invalid_refresh_token", message="Invalid refresh token", status_code=401)

        user = repo.get_user_by_id(db, user_id=rt.user_id)
        if user is None or user.status != "ACTIVE" or user.deleted_at is not None:
            raise AppError(code="unauthorized", message="User is disabled", status_code=401)

        if rt.revoked_at is not None:
            raise AppError(code="invalid_refresh_token", message="Invalid refresh token", status_code=401)
        if rt.expires_at <= now:
            raise AppError(code="refresh_token_expired", message="Refresh token expired", status_code=401)

        # Rotate refresh token: revoke old, insert new.
        repo.revoke_refresh_token(db, token_id=rt.id, now=now)
        new_refresh = create_refresh_token()
        repo.insert_refresh_token(
            db,
            user_id=user.id,
            token_hash=_hash_refresh_token(new_refresh),
            expires_at=_refresh_expires_at(now),
            ip=ip,
            user_agent=user_agent,
        )
        db.commit()

        access = create_access_token(subject=str(user.id))
        scope = resolve_scope(db, user_id=user.id, headers=headers)
        assignments = repo.list_role_assignments(db, user_id=user.id)
        roles = roles_for_scope(assignments=assignments, scope=scope)

        ctx = AuthContext(user_id=user.id, email=user.email, status=user.status, roles=roles, scope=scope)
        return TokenPair(access_token=access, refresh_token=new_refresh), ctx

    def logout(self, db: Session, *, refresh_token: str) -> None:
        now = _now()
        token_hash = _hash_refresh_token(refresh_token)
        rt = repo.get_refresh_token_by_hash(db, token_hash=token_hash)
        if rt is None:
            # Idempotent logout.
            return
        if rt.revoked_at is None:
            repo.revoke_refresh_token(db, token_id=rt.id, now=now)
            db.commit()
