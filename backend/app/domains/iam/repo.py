from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.auth.models import Role, User, UserRole


def get_user_by_email(db: Session, *, email: str) -> User | None:
    stmt = sa.select(User).where(User.email == email, User.deleted_at.is_(None))
    return db.execute(stmt).scalars().first()


def create_user(
    db: Session,
    *,
    email: str,
    phone: str | None,
    password_hash: str,
    status: str,
) -> User:
    user = User(
        id=uuid4(),
        email=email,
        phone=phone,
        password_hash=password_hash,
        status=status,
    )
    db.add(user)
    return user


def list_users_for_tenant(
    db: Session,
    *,
    tenant_id: UUID,
    q: str | None,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[User], int]:
    filters: list[sa.ColumnElement[bool]] = [User.deleted_at.is_(None), UserRole.tenant_id == tenant_id]

    if status:
        filters.append(User.status == status)

    if q:
        like = f"%{q}%"
        filters.append(sa.or_(User.email.ilike(like), User.phone.ilike(like)))

    total = int(
        db.execute(
            sa.select(sa.func.count(sa.distinct(User.id)))
            .select_from(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(*filters)
        ).scalar()
        or 0
    )

    user_ids = (
        sa.select(sa.distinct(User.id).label("user_id"))
        .select_from(User)
        .join(UserRole, UserRole.user_id == User.id)
        .where(*filters)
        .subquery()
    )

    stmt = (
        sa.select(User)
        .where(User.id.in_(sa.select(user_ids.c.user_id)))
        .order_by(User.created_at.desc(), User.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_user_for_tenant(db: Session, *, tenant_id: UUID, user_id: UUID) -> User | None:
    stmt = (
        sa.select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .where(User.id == user_id, UserRole.tenant_id == tenant_id, User.deleted_at.is_(None))
    )
    return db.execute(stmt).scalars().first()


def update_user_status_phone(db: Session, *, user: User, status: str | None, phone: str | None) -> User:
    if status is not None:
        user.status = status
    if phone is not None:
        user.phone = phone
    return user


def get_role_by_code(db: Session, *, role_code: str) -> Role | None:
    stmt = sa.select(Role).where(Role.code == role_code)
    return db.execute(stmt).scalars().first()


def create_user_role(
    db: Session,
    *,
    user_id: UUID,
    tenant_id: UUID,
    company_id: UUID | None,
    branch_id: UUID | None,
    role_id: UUID,
) -> UserRole:
    ur = UserRole(
        user_id=user_id,
        tenant_id=tenant_id,
        company_id=company_id,
        branch_id=branch_id,
        role_id=role_id,
    )
    db.add(ur)
    return ur


def list_user_roles(
    db: Session,
    *,
    user_id: UUID,
    tenant_id: UUID,
) -> list[tuple[str, UUID, UUID | None, UUID | None, datetime]]:
    stmt = (
        sa.select(Role.code, UserRole.tenant_id, UserRole.company_id, UserRole.branch_id, UserRole.created_at)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
        .order_by(Role.code, UserRole.company_id.nullsfirst(), UserRole.branch_id.nullsfirst(), UserRole.created_at)
    )
    return list(db.execute(stmt).all())


def delete_user_role(
    db: Session,
    *,
    user_id: UUID,
    tenant_id: UUID,
    role_id: UUID,
    company_id: UUID | None,
    branch_id: UUID | None,
) -> int:
    stmt = sa.delete(UserRole).where(
        UserRole.user_id == user_id,
        UserRole.tenant_id == tenant_id,
        UserRole.role_id == role_id,
    )

    if company_id is None:
        stmt = stmt.where(UserRole.company_id.is_(None))
    else:
        stmt = stmt.where(UserRole.company_id == company_id)

    if branch_id is None:
        stmt = stmt.where(UserRole.branch_id.is_(None))
    else:
        stmt = stmt.where(UserRole.branch_id == branch_id)

    res = db.execute(stmt)
    return int(res.rowcount or 0)


def get_branch_company(db: Session, *, branch_id: UUID) -> tuple[UUID, UUID] | None:
    row = db.execute(
        sa.text("SELECT tenant_id, company_id FROM tenancy.branches WHERE id = :branch_id"),
        {"branch_id": branch_id},
    ).first()
    if row is None:
        return None
    return row[0], row[1]


def validate_company_in_tenant(db: Session, *, tenant_id: UUID, company_id: UUID) -> bool:
    return (
        db.execute(
            sa.text("SELECT 1 FROM tenancy.companies WHERE id = :company_id AND tenant_id = :tenant_id"),
            {"tenant_id": tenant_id, "company_id": company_id},
        ).first()
        is not None
    )


def validate_branch_in_company(db: Session, *, company_id: UUID, branch_id: UUID) -> bool:
    return (
        db.execute(
            sa.text("SELECT 1 FROM tenancy.branches WHERE id = :branch_id AND company_id = :company_id"),
            {"company_id": company_id, "branch_id": branch_id},
        ).first()
        is not None
    )


def revoke_refresh_tokens_for_user(db: Session, *, user_id: UUID, now: datetime) -> None:
    db.execute(
        sa.text(
            """
            UPDATE iam.refresh_tokens
            SET revoked_at = :now
            WHERE user_id = :user_id
              AND revoked_at IS NULL
            """
        ),
        {"user_id": user_id, "now": now},
    )


def list_roles(db: Session) -> list[Role]:
    return list(db.execute(sa.select(Role).order_by(Role.code)).scalars().all())


def list_permissions(db: Session) -> list[tuple[str, str | None]]:
    rows = db.execute(sa.text("SELECT code, description FROM iam.permissions ORDER BY code")).all()
    return [(r[0], r[1]) for r in rows]

