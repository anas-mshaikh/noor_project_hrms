"""DB vNext (0001): enterprise foundation schemas + core tables.

Revision ID: 888da65cf59f
Revises: f1a8c3d9e2b4
Create Date: 2026-01-29

This migration introduces a clean, enterprise-ready "DB vNext" foundation that
can coexist with the current product modules (attendance/vision/hr/etc.).

Key design goals:
- Modular Postgres schemas for clear domain boundaries:
  - tenancy: tenant/company/branch structure
  - iam: users/roles/permissions and scoped role assignments
  - hr_core: employee 360 master record
  - workflow: generic requests + multi-level approvals
  - dms: document management + expiry alert foundation
- UUID primary keys using `gen_random_uuid()` (pgcrypto).
- `tenant_id` and timestamps on tenant-scoped business tables.
- A reusable `public.set_updated_at()` trigger function and per-table triggers.

Important compatibility note:
- We intentionally DO NOT drop existing tables in this migration. The repo
  already contains multiple domain schemas (core/vision/attendance/hr/...) and
  the running application still depends on them. DB vNext is introduced as a
  new foundation to migrate towards incrementally.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "888da65cf59f"
down_revision = "f1a8c3d9e2b4"
branch_labels = None
depends_on = None


UUID = postgresql.UUID
JSONB = postgresql.JSONB
CITEXT = postgresql.CITEXT
ARRAY = postgresql.ARRAY


def _create_updated_at_trigger(schema: str, table: str) -> None:
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER trg_set_updated_at_{schema}_{table}
            BEFORE UPDATE ON {schema}.{table}
            FOR EACH ROW
            EXECUTE FUNCTION public.set_updated_at();
            """
        )
    )


def upgrade() -> None:
    # Extensions (idempotent). We keep extensions in `public` as recommended.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Schemas (idempotent).
    op.execute("CREATE SCHEMA IF NOT EXISTS tenancy")
    op.execute("CREATE SCHEMA IF NOT EXISTS iam")
    op.execute("CREATE SCHEMA IF NOT EXISTS hr_core")
    op.execute("CREATE SCHEMA IF NOT EXISTS workflow")
    op.execute("CREATE SCHEMA IF NOT EXISTS dms")

    # Reusable updated_at trigger function.
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION public.set_updated_at()
            RETURNS trigger AS $$
            BEGIN
              NEW.updated_at = now();
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    # ---------------------------------------------------------------------
    # tenancy schema
    # ---------------------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="tenancy",
    )
    op.create_index(
        "ix_tenants_status",
        "tenants",
        ["status"],
        unique=False,
        schema="tenancy",
    )
    _create_updated_at_trigger("tenancy", "tenants")

    op.create_table(
        "companies",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=True),
        sa.Column("currency_code", sa.String(length=8), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_companies_tenant_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_companies_tenant_name"),
        schema="tenancy",
    )
    op.create_index(
        "ix_companies_tenant_id",
        "companies",
        ["tenant_id"],
        unique=False,
        schema="tenancy",
    )
    _create_updated_at_trigger("tenancy", "companies")

    op.create_table(
        "branches",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column(
            "address",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_branches_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_branches_company_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("company_id", "name", name="uq_branches_company_name"),
        sa.UniqueConstraint("company_id", "code", name="uq_branches_company_code"),
        schema="tenancy",
    )
    op.create_index(
        "ix_branches_company_id",
        "branches",
        ["company_id"],
        unique=False,
        schema="tenancy",
    )
    _create_updated_at_trigger("tenancy", "branches")

    op.create_table(
        "org_units",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), nullable=True),
        sa.Column("parent_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("unit_type", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_org_units_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_org_units_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_org_units_branch_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["tenancy.org_units.id"],
            name="fk_org_units_parent_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "company_id",
            "parent_id",
            "name",
            name="uq_org_units_company_parent_name",
        ),
        schema="tenancy",
    )
    op.create_index(
        "ix_org_units_company_id",
        "org_units",
        ["company_id"],
        unique=False,
        schema="tenancy",
    )
    op.create_index(
        "ix_org_units_branch_id",
        "org_units",
        ["branch_id"],
        unique=False,
        schema="tenancy",
    )
    _create_updated_at_trigger("tenancy", "org_units")

    op.create_table(
        "job_titles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_job_titles_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_job_titles_company_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("company_id", "name", name="uq_job_titles_company_name"),
        schema="tenancy",
    )
    _create_updated_at_trigger("tenancy", "job_titles")

    op.create_table(
        "grades",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_grades_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_grades_company_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("company_id", "name", name="uq_grades_company_name"),
        schema="tenancy",
    )
    _create_updated_at_trigger("tenancy", "grades")

    # ---------------------------------------------------------------------
    # iam schema
    # ---------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", CITEXT(), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="iam",
    )
    # Partial unique: email must be unique for non-deleted users.
    op.create_index(
        "uq_users_email_not_deleted",
        "users",
        ["email"],
        unique=True,
        schema="iam",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    _create_updated_at_trigger("iam", "users")

    op.create_table(
        "roles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("code", name="uq_roles_code"),
        schema="iam",
    )
    _create_updated_at_trigger("iam", "roles")

    op.create_table(
        "permissions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
        schema="iam",
    )
    _create_updated_at_trigger("iam", "permissions")

    op.create_table(
        "role_permissions",
        sa.Column("role_id", UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["iam.roles.id"],
            name="fk_role_permissions_role_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["iam.permissions.id"],
            name="fk_role_permissions_permission_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permissions"),
        schema="iam",
    )

    op.create_table(
        "user_roles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", UUID(as_uuid=True), nullable=True),
        sa.Column("role_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["iam.users.id"],
            name="fk_user_roles_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_user_roles_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_user_roles_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_user_roles_branch_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["iam.roles.id"],
            name="fk_user_roles_role_id",
            ondelete="CASCADE",
        ),
        schema="iam",
    )
    # Ensure a user can't be assigned the same role twice for the same scope.
    # PKs cannot include NULL columns in Postgres, so we model scope uniqueness
    # using "UNIQUE NULLS NOT DISTINCT" instead.
    op.execute(
        sa.text(
            """
            ALTER TABLE iam.user_roles
            ADD CONSTRAINT uq_user_roles_scope
            UNIQUE NULLS NOT DISTINCT (user_id, tenant_id, role_id, company_id, branch_id);
            """
        )
    )
    op.create_index(
        "ix_user_roles_user_id",
        "user_roles",
        ["user_id"],
        unique=False,
        schema="iam",
    )
    op.create_index(
        "ix_user_roles_tenant_id",
        "user_roles",
        ["tenant_id"],
        unique=False,
        schema="iam",
    )

    op.create_table(
        "api_tokens",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_api_tokens_tenant_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_api_tokens_tenant_name"),
        schema="iam",
    )
    op.create_index(
        "ix_api_tokens_tenant_id_status",
        "api_tokens",
        ["tenant_id", "status"],
        unique=False,
        schema="iam",
    )
    _create_updated_at_trigger("iam", "api_tokens")

    # ---------------------------------------------------------------------
    # hr_core schema
    # ---------------------------------------------------------------------
    op.create_table(
        "persons",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("first_name", sa.String(length=200), nullable=False),
        sa.Column("last_name", sa.String(length=200), nullable=False),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column("nationality", sa.String(length=100), nullable=True),
        sa.Column("email", CITEXT(), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column(
            "address",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_persons_tenant_id",
            ondelete="CASCADE",
        ),
        schema="hr_core",
    )
    op.create_index(
        "ix_persons_tenant_id",
        "persons",
        ["tenant_id"],
        unique=False,
        schema="hr_core",
    )
    _create_updated_at_trigger("hr_core", "persons")

    op.create_table(
        "employees",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", UUID(as_uuid=True), nullable=False),
        sa.Column("employee_code", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column("join_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_hr_employees_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_hr_employees_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["hr_core.persons.id"],
            name="fk_hr_employees_person_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "company_id",
            "employee_code",
            name="uq_hr_employees_company_employee_code",
        ),
        schema="hr_core",
    )
    op.create_index(
        "ix_hr_employees_tenant_id_status",
        "employees",
        ["tenant_id", "status"],
        unique=False,
        schema="hr_core",
    )
    _create_updated_at_trigger("hr_core", "employees")

    op.create_table(
        "employee_employment",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), nullable=False),
        sa.Column("org_unit_id", UUID(as_uuid=True), nullable=True),
        sa.Column("job_title_id", UUID(as_uuid=True), nullable=True),
        sa.Column("grade_id", UUID(as_uuid=True), nullable=True),
        sa.Column("manager_employee_id", UUID(as_uuid=True), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_employee_employment_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_employee_employment_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_employee_employment_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_employee_employment_branch_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"],
            ["tenancy.org_units.id"],
            name="fk_employee_employment_org_unit_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["job_title_id"],
            ["tenancy.job_titles.id"],
            name="fk_employee_employment_job_title_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["grade_id"],
            ["tenancy.grades.id"],
            name="fk_employee_employment_grade_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["manager_employee_id"],
            ["hr_core.employees.id"],
            name="fk_employee_employment_manager_employee_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_employee_employment_end_gte_start",
        ),
        schema="hr_core",
    )
    op.create_index(
        "ix_employee_employment_employee_id_start_date",
        "employee_employment",
        ["employee_id", "start_date"],
        unique=False,
        schema="hr_core",
        postgresql_using="btree",
    )
    op.create_index(
        "ix_employee_employment_manager_current",
        "employee_employment",
        ["manager_employee_id"],
        unique=False,
        schema="hr_core",
        postgresql_where=sa.text("end_date IS NULL"),
    )
    _create_updated_at_trigger("hr_core", "employee_employment")

    op.create_table(
        "employee_user_links",
        sa.Column("employee_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_employee_user_links_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["iam.users.id"],
            name="fk_employee_user_links_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("employee_id", name="pk_employee_user_links"),
        sa.UniqueConstraint("user_id", name="uq_employee_user_links_user_id"),
        schema="hr_core",
    )
    _create_updated_at_trigger("hr_core", "employee_user_links")

    op.create_table(
        "employee_contracts",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", UUID(as_uuid=True), nullable=False),
        sa.Column("contract_type", sa.String(length=64), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("probation_end_date", sa.Date(), nullable=True),
        sa.Column("wage_type", sa.String(length=32), nullable=True),
        sa.Column("base_salary", sa.Numeric(), nullable=True),
        sa.Column("currency_code", sa.String(length=8), nullable=True),
        sa.Column(
            "terms",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_employee_contracts_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_employee_contracts_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_employee_contracts_employee_id",
            ondelete="CASCADE",
        ),
        schema="hr_core",
    )
    op.create_index(
        "ix_employee_contracts_employee_id",
        "employee_contracts",
        ["employee_id"],
        unique=False,
        schema="hr_core",
    )
    _create_updated_at_trigger("hr_core", "employee_contracts")

    op.create_table(
        "employee_dependents",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("relationship", sa.String(length=64), nullable=True),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_employee_dependents_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_employee_dependents_employee_id",
            ondelete="CASCADE",
        ),
        schema="hr_core",
    )
    op.create_index(
        "ix_employee_dependents_employee_id",
        "employee_dependents",
        ["employee_id"],
        unique=False,
        schema="hr_core",
    )
    _create_updated_at_trigger("hr_core", "employee_dependents")

    op.create_table(
        "employee_bank_accounts",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", UUID(as_uuid=True), nullable=False),
        sa.Column("iban", sa.String(length=64), nullable=True),
        sa.Column("account_number", sa.String(length=64), nullable=True),
        sa.Column("bank_name", sa.String(length=200), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_employee_bank_accounts_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_employee_bank_accounts_employee_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "(iban IS NOT NULL) OR (account_number IS NOT NULL)",
            name="ck_employee_bank_accounts_one_identifier",
        ),
        schema="hr_core",
    )
    op.create_index(
        "ix_employee_bank_accounts_employee_id",
        "employee_bank_accounts",
        ["employee_id"],
        unique=False,
        schema="hr_core",
    )
    _create_updated_at_trigger("hr_core", "employee_bank_accounts")

    op.create_table(
        "employee_government_ids",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", UUID(as_uuid=True), nullable=False),
        sa.Column("id_type", sa.String(length=64), nullable=False),
        sa.Column("id_number", sa.String(length=128), nullable=False),
        sa.Column("issued_at", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("issuing_country", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_employee_government_ids_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_employee_government_ids_employee_id",
            ondelete="CASCADE",
        ),
        schema="hr_core",
    )
    op.create_index(
        "ix_employee_government_ids_employee_id",
        "employee_government_ids",
        ["employee_id"],
        unique=False,
        schema="hr_core",
    )
    op.create_index(
        "ix_employee_government_ids_tenant_expires_at",
        "employee_government_ids",
        ["tenant_id", "expires_at"],
        unique=False,
        schema="hr_core",
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )
    _create_updated_at_trigger("hr_core", "employee_government_ids")

    # ---------------------------------------------------------------------
    # dms schema
    # ---------------------------------------------------------------------
    op.create_table(
        "files",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("storage_provider", sa.String(length=32), nullable=False),
        sa.Column("bucket", sa.Text(), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_files_tenant_id",
            ondelete="CASCADE",
        ),
        schema="dms",
    )
    op.create_index(
        "ix_files_tenant_id",
        "files",
        ["tenant_id"],
        unique=False,
        schema="dms",
    )
    _create_updated_at_trigger("dms", "files")

    op.create_table(
        "document_types",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "requires_expiry",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_document_types_tenant_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "code", name="uq_document_types_tenant_code"),
        schema="dms",
    )
    _create_updated_at_trigger("dms", "document_types")

    op.create_table(
        "documents",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_type_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column("issued_at", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column(
            "metadata",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_documents_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_type_id"],
            ["dms.document_types.id"],
            name="fk_documents_document_type_id",
            ondelete="RESTRICT",
        ),
        schema="dms",
    )
    op.create_index(
        "ix_documents_tenant_expires_at",
        "documents",
        ["tenant_id", "expires_at"],
        unique=False,
        schema="dms",
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )
    _create_updated_at_trigger("dms", "documents")

    op.create_table(
        "document_versions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_document_versions_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["dms.documents.id"],
            name="fk_document_versions_document_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["dms.files.id"],
            name="fk_document_versions_file_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("document_id", "version", name="uq_document_versions_doc_v"),
        schema="dms",
    )
    op.create_index(
        "ix_document_versions_document_id",
        "document_versions",
        ["document_id"],
        unique=False,
        schema="dms",
    )

    op.create_table(
        "document_links",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_document_links_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["dms.documents.id"],
            name="fk_document_links_document_id",
            ondelete="CASCADE",
        ),
        schema="dms",
    )
    op.create_index(
        "ix_document_links_tenant_entity",
        "document_links",
        ["tenant_id", "entity_type", "entity_id"],
        unique=False,
        schema="dms",
    )

    op.create_table(
        "expiry_rules",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_type_id", UUID(as_uuid=True), nullable=True),
        sa.Column("days_before", sa.Integer(), nullable=False),
        sa.Column(
            "notify_roles",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_expiry_rules_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_type_id"],
            ["dms.document_types.id"],
            name="fk_expiry_rules_document_type_id",
            ondelete="SET NULL",
        ),
        schema="dms",
    )
    op.create_index(
        "ix_expiry_rules_tenant_id",
        "expiry_rules",
        ["tenant_id"],
        unique=False,
        schema="dms",
    )
    _create_updated_at_trigger("dms", "expiry_rules")

    op.create_table(
        "expiry_events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "fired_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("channel", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_expiry_events_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["dms.documents.id"],
            name="fk_expiry_events_document_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["dms.expiry_rules.id"],
            name="fk_expiry_events_rule_id",
            ondelete="CASCADE",
        ),
        schema="dms",
    )
    op.create_index(
        "ix_expiry_events_tenant_id_fired_at",
        "expiry_events",
        ["tenant_id", "fired_at"],
        unique=False,
        schema="dms",
    )

    # ---------------------------------------------------------------------
    # workflow schema
    # ---------------------------------------------------------------------
    op.create_table(
        "request_types",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("code", name="uq_request_types_code"),
        schema="workflow",
    )

    op.create_table(
        "workflow_definitions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=True),
        sa.Column("request_type_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_workflow_definitions_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_workflow_definitions_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["request_type_id"],
            ["workflow.request_types.id"],
            name="fk_workflow_definitions_request_type_id",
            ondelete="RESTRICT",
        ),
        schema="workflow",
    )
    op.create_index(
        "ix_workflow_definitions_tenant_active",
        "workflow_definitions",
        ["tenant_id", "is_active"],
        unique=False,
        schema="workflow",
    )
    _create_updated_at_trigger("workflow", "workflow_definitions")

    op.create_table(
        "workflow_definition_steps",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workflow_definition_id", UUID(as_uuid=True), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("approver_mode", sa.String(length=32), nullable=False),
        sa.Column("role_code", sa.String(length=64), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["workflow_definition_id"],
            ["workflow.workflow_definitions.id"],
            name="fk_workflow_definition_steps_definition_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["iam.users.id"],
            name="fk_workflow_definition_steps_user_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "workflow_definition_id",
            "step_order",
            name="uq_workflow_definition_steps_order",
        ),
        schema="workflow",
    )
    _create_updated_at_trigger("workflow", "workflow_definition_steps")

    op.create_table(
        "requests",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), nullable=True),
        sa.Column("request_type_id", UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_definition_id", UUID(as_uuid=True), nullable=False),
        sa.Column("requester_employee_id", UUID(as_uuid=True), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "current_step",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "payload",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_requests_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_requests_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_requests_branch_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["request_type_id"],
            ["workflow.request_types.id"],
            name="fk_requests_request_type_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_definition_id"],
            ["workflow.workflow_definitions.id"],
            name="fk_requests_workflow_definition_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requester_employee_id"],
            ["hr_core.employees.id"],
            name="fk_requests_requester_employee_id",
            ondelete="RESTRICT",
        ),
        schema="workflow",
    )
    op.create_index(
        "ix_requests_tenant_status_type",
        "requests",
        ["tenant_id", "status", "request_type_id"],
        unique=False,
        schema="workflow",
    )
    op.create_index(
        "ix_requests_requester_created_at",
        "requests",
        ["requester_employee_id", "created_at"],
        unique=False,
        schema="workflow",
    )
    _create_updated_at_trigger("workflow", "requests")

    op.create_table(
        "request_steps",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("approver_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["workflow.requests.id"],
            name="fk_request_steps_request_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["approver_user_id"],
            ["iam.users.id"],
            name="fk_request_steps_approver_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "request_id",
            "step_order",
            name="uq_request_steps_request_order",
        ),
        schema="workflow",
    )
    op.create_index(
        "ix_request_steps_approver_decided_at",
        "request_steps",
        ["approver_user_id", "decided_at"],
        unique=False,
        schema="workflow",
    )
    op.create_index(
        "ix_request_steps_request_id",
        "request_steps",
        ["request_id"],
        unique=False,
        schema="workflow",
    )

    op.create_table(
        "request_comments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["workflow.requests.id"],
            name="fk_request_comments_request_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["iam.users.id"],
            name="fk_request_comments_author_user_id",
            ondelete="CASCADE",
        ),
        schema="workflow",
    )
    op.create_index(
        "ix_request_comments_request_id_created_at",
        "request_comments",
        ["request_id", "created_at"],
        unique=False,
        schema="workflow",
    )

    op.create_table(
        "request_attachments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_request_attachments_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["workflow.requests.id"],
            name="fk_request_attachments_request_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["dms.files.id"],
            name="fk_request_attachments_file_id",
            ondelete="CASCADE",
        ),
        schema="workflow",
    )
    op.create_index(
        "ix_request_attachments_request_id",
        "request_attachments",
        ["request_id"],
        unique=False,
        schema="workflow",
    )

    op.create_table(
        "notification_outbox",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("recipient_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("template_code", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_notification_outbox_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["iam.users.id"],
            name="fk_notification_outbox_recipient_user_id",
            ondelete="CASCADE",
        ),
        schema="workflow",
    )
    op.create_index(
        "ix_notification_outbox_tenant_status_retry",
        "notification_outbox",
        ["tenant_id", "status", "next_retry_at"],
        unique=False,
        schema="workflow",
    )
    _create_updated_at_trigger("workflow", "notification_outbox")


def downgrade() -> None:
    # In dev, a "clean downgrade" means dropping the new schemas and all objects
    # within them. We intentionally do not drop shared extensions.
    op.execute("DROP SCHEMA IF EXISTS workflow CASCADE")
    op.execute("DROP SCHEMA IF EXISTS dms CASCADE")
    op.execute("DROP SCHEMA IF EXISTS hr_core CASCADE")
    op.execute("DROP SCHEMA IF EXISTS iam CASCADE")
    op.execute("DROP SCHEMA IF EXISTS tenancy CASCADE")
