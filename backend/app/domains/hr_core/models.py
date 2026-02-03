from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import User
from app.db.base import Base
# Register Tenancy tables in the shared metadata; HR models reference them via FK strings.
from app.domains.tenancy import models as _tenancy_models  # noqa: F401


class Person(Base):
    __tablename__ = "persons"
    __table_args__ = {"schema": "hr_core"}

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)

    first_name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    last_name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    dob: Mapped[date | None] = mapped_column(sa.Date(), nullable=True)
    nationality: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(postgresql.CITEXT(), nullable=True)
    phone: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    address: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        sa.UniqueConstraint("company_id", "employee_code", name="uq_hr_employees_company_employee_code"),
        {"schema": "hr_core"},
    )

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    company_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    person_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("hr_core.persons.id", ondelete="CASCADE"),
        nullable=False,
    )

    employee_code: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default=sa.text("'ACTIVE'"))
    join_date: Mapped[date | None] = mapped_column(sa.Date(), nullable=True)
    termination_date: Mapped[date | None] = mapped_column(sa.Date(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    person: Mapped[Person] = relationship(Person, lazy="joined")
    employments: Mapped[list["EmployeeEmployment"]] = relationship(
        "EmployeeEmployment",
        foreign_keys="EmployeeEmployment.employee_id",
        order_by="desc(EmployeeEmployment.start_date)",
        back_populates="employee",
        lazy="selectin",
    )


class EmployeeEmployment(Base):
    __tablename__ = "employee_employment"
    __table_args__ = (
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_employee_employment_end_gte_start"),
        {"schema": "hr_core"},
    )

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    company_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("hr_core.employees.id", ondelete="CASCADE"),
        nullable=False,
    )

    branch_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("tenancy.branches.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_unit_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("tenancy.org_units.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_title_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("tenancy.job_titles.id", ondelete="SET NULL"),
        nullable=True,
    )
    grade_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("tenancy.grades.id", ondelete="SET NULL"),
        nullable=True,
    )

    manager_employee_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("hr_core.employees.id", ondelete="SET NULL"),
        nullable=True,
    )

    start_date: Mapped[date] = mapped_column(sa.Date(), nullable=False)
    end_date: Mapped[date | None] = mapped_column(sa.Date(), nullable=True)
    is_primary: Mapped[bool | None] = mapped_column(sa.Boolean(), nullable=True, server_default=sa.text("true"))

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    employee: Mapped[Employee] = relationship(Employee, foreign_keys=[employee_id], back_populates="employments", lazy="joined")
    manager_employee: Mapped[Employee | None] = relationship(Employee, foreign_keys=[manager_employee_id], lazy="joined", viewonly=True)


class EmployeeUserLink(Base):
    __tablename__ = "employee_user_links"
    __table_args__ = {"schema": "hr_core"}

    employee_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("hr_core.employees.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("iam.users.id", ondelete="CASCADE"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    employee: Mapped[Employee] = relationship(Employee, lazy="joined")
    user: Mapped[User] = relationship(User, lazy="joined", viewonly=True)
