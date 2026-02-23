"""Attendance punching v1: seed permissions.

Revision ID: 7d5dc0b6d1ff
Revises: b3ef9f746c38
Create Date: 2026-02-20

This migration seeds:
- permission vocabulary for attendance punching + time/payroll views
- default role mappings for v1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "7d5dc0b6d1ff"
down_revision = "b3ef9f746c38"
branch_labels = None
depends_on = None


PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("attendance:punch:submit", "Submit attendance punches (ESS)"),
    ("attendance:punch:read", "Read own punch state and day minutes (ESS)"),
    ("attendance:time:read", "Read team attendance time views"),
    ("attendance:settings:write", "Manage attendance punch settings"),
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

    all_codes = tuple(code for code, _desc in PERMISSIONS)

    # ADMIN: full access.
    _grant("ADMIN", all_codes)

    # HR roles: settings + reporting (team time views).
    _grant("HR_ADMIN", ("attendance:settings:write", "attendance:time:read"))
    _grant("HR_MANAGER", ("attendance:settings:write", "attendance:time:read"))

    # Managers: team time views (v1; payroll preview).
    _grant("MANAGER", ("attendance:time:read",))

    # Employees: submit/read own punches.
    _grant("EMPLOYEE", ("attendance:punch:submit", "attendance:punch:read"))


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
              AND r.code IN ('ADMIN','HR_ADMIN','HR_MANAGER','MANAGER','EMPLOYEE')
              AND p.code IN ({quoted})
            """
        )
    )
    op.execute(sa.text(f"DELETE FROM iam.permissions WHERE code IN ({quoted})"))

