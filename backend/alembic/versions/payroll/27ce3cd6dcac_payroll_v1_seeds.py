"""Payroll foundation v1: seed permissions, workflow request type, and PAYSLIP doc type.

Revision ID: 27ce3cd6dcac
Revises: 0cb7c87299c1
Create Date: 2026-02-21

This migration seeds:
- Payroll permission vocabulary (setup, payrun, payslips).
- Default role mappings (least-privilege).
- Workflow request type `PAYRUN_APPROVAL` (idempotent insert).
- DMS document type `PAYSLIP` for all existing tenants (idempotent insert).

Notes:
- Seeds are intentionally idempotent via `ON CONFLICT DO NOTHING` to keep
  environments consistent across re-deploys.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "27ce3cd6dcac"
down_revision = "0cb7c87299c1"
branch_labels = None
depends_on = None


PERMISSIONS: tuple[tuple[str, str], ...] = (
    # Setup
    ("payroll:calendar:read", "Read payroll calendars and periods"),
    ("payroll:calendar:write", "Write payroll calendars and periods"),
    ("payroll:component:read", "Read payroll components"),
    ("payroll:component:write", "Write payroll components"),
    ("payroll:structure:read", "Read salary structures"),
    ("payroll:structure:write", "Write salary structures"),
    ("payroll:compensation:read", "Read employee compensation"),
    ("payroll:compensation:write", "Write employee compensation"),
    # Payrun lifecycle
    ("payroll:payrun:generate", "Generate a payrun for a period"),
    ("payroll:payrun:read", "Read payruns and payrun items"),
    ("payroll:payrun:submit", "Submit a payrun for approval"),
    ("payroll:payrun:publish", "Publish an approved payrun (generate payslips)"),
    ("payroll:payrun:export", "Export a payrun (CSV placeholder)"),
    # Payslips
    ("payroll:payslip:read", "Read own payslips (ESS)"),
    ("payroll:payslip:publish", "Publish payslips (internal)"),
    # Reporting
    ("payroll:admin:read", "Payroll reporting read access"),
)


def _seed_permissions() -> None:
    """Insert missing permission codes (idempotent)."""

    for code, desc in PERMISSIONS:
        op.execute(
            sa.text(
                """
                INSERT INTO iam.permissions (code, description)
                VALUES (:code, :description)
                ON CONFLICT (code) DO NOTHING
                """
            ).bindparams(
                sa.bindparam("code", value=code),
                sa.bindparam("description", value=desc),
            )
        )


def _grant(role_code: str, perm_codes: tuple[str, ...]) -> None:
    """Grant a list of permission codes to a role code (idempotent)."""

    if not perm_codes:
        return
    quoted = ", ".join(f"'{c}'" for c in perm_codes)
    op.execute(
        sa.text(
            f"""
            INSERT INTO iam.role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM iam.roles r
            JOIN iam.permissions p ON p.code IN ({quoted})
            WHERE r.code = :role_code
            ON CONFLICT DO NOTHING
            """
        ).bindparams(sa.bindparam("role_code", value=role_code))
    )


def upgrade() -> None:
    _seed_permissions()

    all_payroll = tuple(code for code, _desc in PERMISSIONS)

    # ADMIN: full payroll access.
    _grant("ADMIN", all_payroll)

    # HR_ADMIN: full payroll administration access (v1 does not introduce FINANCE role).
    _grant("HR_ADMIN", all_payroll)

    # HR_MANAGER: read-only visibility into payruns/reporting (no mutate).
    _grant("HR_MANAGER", ("payroll:admin:read", "payroll:payrun:read"))

    # EMPLOYEE: self payslip read only.
    _grant("EMPLOYEE", ("payroll:payslip:read",))

    # Workflow request type: PAYRUN_APPROVAL.
    op.execute(
        sa.text(
            """
            INSERT INTO workflow.request_types (code, name, description)
            VALUES (
              'PAYRUN_APPROVAL',
              'Payrun Approval',
              'Payroll payrun approval request'
            )
            ON CONFLICT (code) DO NOTHING
            """
        )
    )

    # Seed DMS document type: PAYSLIP for all existing tenants.
    #
    # Publish logic will still "ensure exists" at runtime, to cover tenants
    # created after this migration.
    op.execute(
        sa.text(
            """
            INSERT INTO dms.document_types (tenant_id, code, name, requires_expiry, is_active)
            SELECT t.id, 'PAYSLIP', 'Payslip', false, true
            FROM tenancy.tenants t
            ON CONFLICT (tenant_id, code) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    codes = tuple(code for code, _desc in PERMISSIONS)
    quoted = ", ".join(f"'{c}'" for c in codes)

    op.execute(
        sa.text(
            f"""
            DELETE FROM iam.role_permissions rp
            USING iam.roles r, iam.permissions p
            WHERE rp.role_id = r.id
              AND rp.permission_id = p.id
              AND r.code IN ('ADMIN','HR_ADMIN','HR_MANAGER','EMPLOYEE')
              AND p.code IN ({quoted})
            """
        )
    )
    op.execute(sa.text(f"DELETE FROM iam.permissions WHERE code IN ({quoted})"))

    # Best-effort cleanup of request type and document type.
    op.execute(sa.text("DELETE FROM workflow.request_types WHERE code = 'PAYRUN_APPROVAL'"))
    op.execute(sa.text("DELETE FROM dms.document_types WHERE code = 'PAYSLIP'"))

