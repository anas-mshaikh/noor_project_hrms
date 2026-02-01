from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "tenancy"}

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default=sa.text("'ACTIVE'"))

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    created_by: Mapped[UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    updated_by: Mapped[UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = {"schema": "tenancy"}

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(sa.String(8), nullable=True)
    timezone: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default=sa.text("'ACTIVE'"))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = {"schema": "tenancy"}

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    company_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    code: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    timezone: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    address: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default=sa.text("'ACTIVE'"))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class OrgUnit(Base):
    __tablename__ = "org_units"
    __table_args__ = {"schema": "tenancy"}

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    company_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    parent_id: Mapped[UUID | None] = mapped_column(postgresql.UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    unit_type: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class JobTitle(Base):
    __tablename__ = "job_titles"
    __table_args__ = {"schema": "tenancy"}

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    company_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = {"schema": "tenancy"}

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    company_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    level: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

