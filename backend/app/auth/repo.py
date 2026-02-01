from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.auth.models import RefreshToken, Role, User, UserRole


def get_user_by_email(db: Session, *, email: str) -> User | None:
    stmt = sa.select(User).where(User.email == email, User.deleted_at.is_(None))
    return db.execute(stmt).scalars().first()


def get_user_by_id(db: Session, *, user_id: UUID) -> User | None:
    stmt = sa.select(User).where(User.id == user_id, User.deleted_at.is_(None))
    return db.execute(stmt).scalars().first()


def list_role_assignments(db: Session, *, user_id: UUID) -> list[tuple[UUID, UUID | None, UUID | None, str]]:
    """
    Returns (tenant_id, company_id, branch_id, role_code) for the user.
    """

    stmt = (
        sa.select(UserRole.tenant_id, UserRole.company_id, UserRole.branch_id, Role.code)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user_id)
    )
    return list(db.execute(stmt).all())


def insert_refresh_token(
    db: Session,
    *,
    user_id: UUID,
    token_hash: str,
    expires_at: datetime,
    ip: str | None,
    user_agent: str | None,
) -> RefreshToken:
    rt = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(rt)
    return rt


def get_refresh_token_by_hash(db: Session, *, token_hash: str) -> RefreshToken | None:
    stmt = sa.select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    return db.execute(stmt).scalars().first()


def revoke_refresh_token(db: Session, *, token_id: UUID, now: datetime) -> None:
    stmt = (
        sa.update(RefreshToken)
        .where(RefreshToken.id == token_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.execute(stmt)

