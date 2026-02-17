"""DB vNext (0004): drop legacy identity duplicates.

Revision ID: b3f7a9d2c4e1
Revises: aca6f7cb881b
Create Date: 2026-01-30

Hard cutover strategy:
- DB vNext schemas are the ONLY canonical masters for:
  - tenancy (tenant/company/branch/org)
  - iam (users/roles/permissions)
  - hr_core (person/employee)
  - workflow (requests/approvals)
  - dms (files/documents)

Since this environment has no real customer data, we intentionally delete legacy
master tables that duplicate vNext concepts, rather than migrating data.

Safety rules:
- DO NOT drop `public.alembic_version`.
- Assert vNext tables exist before dropping legacy objects.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "b3f7a9d2c4e1"
down_revision = "aca6f7cb881b"
branch_labels = None
depends_on = None


_VNEXT_ASSERT_TABLES: tuple[str, ...] = (
    "tenancy.tenants",
    "tenancy.companies",
    "tenancy.branches",
    "iam.users",
    "iam.roles",
    "hr_core.persons",
    "hr_core.employees",
    "workflow.requests",
    "dms.files",
    "dms.documents",
)


def _assert_vnext_present(conn) -> None:
    missing: list[str] = []
    for fqtn in _VNEXT_ASSERT_TABLES:
        exists = conn.execute(sa.text("SELECT to_regclass(:fqtn)"), {"fqtn": fqtn}).scalar()
        if exists is None:
            missing.append(fqtn)
    if missing:
        raise RuntimeError(
            "Refusing to drop legacy identity tables because vNext tables are missing: "
            + ", ".join(missing)
        )


def _print_legacy_master_inventory(conn) -> None:
    # Discovery-only: helps identify residual duplicates in dev DBs.
    # We keep this lightweight and exclude system + vNext schemas.
    patterns = [
        "%organization%",
        "%store%",
        "%branch%",
        "%employee%",
        "%user%",
        "%role%",
        "%document%",
    ]
    rows = conn.execute(
        sa.text(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema NOT IN (
                'pg_catalog', 'information_schema',
                'tenancy', 'iam', 'hr_core', 'workflow', 'dms'
              )
              AND (
                table_name ILIKE :p1 OR
                table_name ILIKE :p2 OR
                table_name ILIKE :p3 OR
                table_name ILIKE :p4 OR
                table_name ILIKE :p5 OR
                table_name ILIKE :p6 OR
                table_name ILIKE :p7
              )
            ORDER BY table_schema, table_name
            """
        ),
        {f"p{i+1}": patterns[i] for i in range(len(patterns))},
    ).fetchall()

    print(f"[db_vnext_0004] legacy master inventory rows={len(rows)}")
    for schema, table in rows:
        print(f"[db_vnext_0004] legacy candidate: {schema}.{table}")


def upgrade() -> None:
    conn = op.get_bind()

    _assert_vnext_present(conn)
    _print_legacy_master_inventory(conn)

    # ------------------------------------------------------------------
    # Drop legacy identity masters (duplicates of vNext tenancy/hr_core/iam).
    #
    # `core.*` previously held:
    # - organizations (old tenant/org root)
    # - stores (old branch/store)
    # - employees (old employee master)
    #
    # All modules must now reference:
    # - tenancy.tenants / tenancy.branches
    # - hr_core.employees
    # ------------------------------------------------------------------
    op.execute("DROP SCHEMA IF EXISTS core CASCADE")

    # Defensive cleanup for partially-applied/dev DBs that still have old public tables.
    op.execute("DROP TABLE IF EXISTS public.organizations CASCADE")
    op.execute("DROP TABLE IF EXISTS public.stores CASCADE")
    op.execute("DROP TABLE IF EXISTS public.employees CASCADE")

    # Duplicate "documents" table in hr module: vNext DMS is canonical.
    op.execute("DROP TABLE IF EXISTS hr.hr_employee_documents CASCADE")


def downgrade() -> None:
    raise NotImplementedError(
        "db_vnext_0004_drop_legacy_identity is destructive by design; downgrade is not supported."
    )
