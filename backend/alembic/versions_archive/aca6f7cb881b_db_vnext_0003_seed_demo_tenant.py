"""DB vNext (0003): seed a demo tenant/company/branch.

Revision ID: aca6f7cb881b
Revises: fc4c56b52118
Create Date: 2026-01-29

Creates a small demo tenant hierarchy to enable immediate local development and
smoke-testing of the vNext schemas.

This seed is optional for production deployments; it is intended for dev/demo.
"""

from __future__ import annotations

import os
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "aca6f7cb881b"
down_revision = "fc4c56b52118"
branch_labels = None
depends_on = None


DEMO_TENANT_ID = "a8074bcb-f62c-4bd1-9886-06e21dc1869e"
DEMO_COMPANY_ID = "d0a5520b-4c14-44fb-bdd4-35d1b5dc8e1b"
DEMO_BRANCH_ID = "7651b5f1-0a5b-42d1-8830-b405a4441292"

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # Demo seed is optional and should not run in production-like environments.
    # Note: Alembic migrations are usually deterministic; this opt-in gate exists
    # only because this migration inserts demo data (not DDL).
    seed_enabled = os.getenv("DB_VNEXT_SEED_DEMO_TENANT", "").strip().lower() in {"1", "true", "yes", "y"}
    if not seed_enabled:
        return

    conn = op.get_bind()
    already_seeded = (
        conn.execute(
            sa.text("SELECT 1 FROM tenancy.tenants WHERE id = :id"),
            {"id": uuid.UUID(DEMO_TENANT_ID)},
        ).first()
        is not None
    )
    if already_seeded:
        return

    # NOTE: psycopg (and other DBAPIs) may reject multiple SQL statements when
    # parameters are bound (prepared statements). Keep statements single.
    op.execute(
        sa.text(
            """
            INSERT INTO tenancy.tenants (id, name, status)
            VALUES (:tenant_id, 'Demo Tenant', 'ACTIVE')
            """
        ).bindparams(
            sa.bindparam(
                "tenant_id", type_=UUID, value=uuid.UUID(DEMO_TENANT_ID)
            )
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO tenancy.companies (
              id, tenant_id, name, legal_name, currency_code, timezone, status
            ) VALUES (
              :company_id, :tenant_id, 'Demo Company', 'Demo Company LLC', 'SAR', 'Asia/Riyadh', 'ACTIVE'
            )
            """
        ).bindparams(
            sa.bindparam(
                "tenant_id", type_=UUID, value=uuid.UUID(DEMO_TENANT_ID)
            ),
            sa.bindparam(
                "company_id", type_=UUID, value=uuid.UUID(DEMO_COMPANY_ID)
            ),
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO tenancy.branches (
              id, tenant_id, company_id, name, code, timezone, address, status
            ) VALUES (
              :branch_id, :tenant_id, :company_id, 'Riyadh Branch', 'RYD', 'Asia/Riyadh', '{}'::jsonb, 'ACTIVE'
            )
            """
        ).bindparams(
            sa.bindparam(
                "tenant_id", type_=UUID, value=uuid.UUID(DEMO_TENANT_ID)
            ),
            sa.bindparam(
                "company_id", type_=UUID, value=uuid.UUID(DEMO_COMPANY_ID)
            ),
            sa.bindparam(
                "branch_id", type_=UUID, value=uuid.UUID(DEMO_BRANCH_ID)
            ),
        )
    )

    # Seed tenant-scoped document types for demo.
    op.execute(
        sa.text(
            """
            INSERT INTO dms.document_types (tenant_id, code, name, requires_expiry)
            VALUES
              (:tenant_id, 'ID', 'National ID', true),
              (:tenant_id, 'PASSPORT', 'Passport', true),
              (:tenant_id, 'VISA', 'Visa / Residency', true),
              (:tenant_id, 'CONTRACT', 'Employment Contract', false),
              (:tenant_id, 'BANK', 'Bank Details', false),
              (:tenant_id, 'PHOTO', 'Employee Photo', false)
            ;
            """
        ).bindparams(
            sa.bindparam(
                "tenant_id", type_=UUID, value=uuid.UUID(DEMO_TENANT_ID)
            )
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM dms.document_types WHERE tenant_id = :tenant_id").bindparams(
            sa.bindparam("tenant_id", type_=UUID, value=uuid.UUID(DEMO_TENANT_ID))
        )
    )
    op.execute(
        sa.text("DELETE FROM tenancy.branches WHERE id = :branch_id").bindparams(
            sa.bindparam("branch_id", type_=UUID, value=uuid.UUID(DEMO_BRANCH_ID))
        )
    )
    op.execute(
        sa.text("DELETE FROM tenancy.companies WHERE id = :company_id").bindparams(
            sa.bindparam("company_id", type_=UUID, value=uuid.UUID(DEMO_COMPANY_ID))
        )
    )
    op.execute(
        sa.text("DELETE FROM tenancy.tenants WHERE id = :tenant_id").bindparams(
            sa.bindparam("tenant_id", type_=UUID, value=uuid.UUID(DEMO_TENANT_ID))
        )
    )
