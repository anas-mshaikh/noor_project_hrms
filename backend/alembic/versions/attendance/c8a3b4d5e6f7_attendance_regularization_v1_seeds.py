"""Attendance regularization v1: seed permissions and workflow request type.

Revision ID: c8a3b4d5e6f7
Revises: b7f2a3c4d5e6
Create Date: 2026-02-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c8a3b4d5e6f7"
down_revision = "b7f2a3c4d5e6"
branch_labels = None
depends_on = None


PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("attendance:correction:submit", "Submit attendance correction requests"),
    ("attendance:correction:read", "Read own attendance correction requests"),
    ("attendance:team:read", "Read team attendance calendar/overrides"),
    ("attendance:admin:read", "Read attendance correction admin reports"),
)


def _seed_permissions() -> None:
    for code, desc in PERMISSIONS:
        op.execute(
            sa.text(
                """
                INSERT INTO iam.permissions (code, description)
                VALUES (:code, :description)
                ON CONFLICT (code) DO NOTHING
                """
            ).bindparams(sa.bindparam("code", value=code), sa.bindparam("description", value=desc))
        )


def _grant(role_code: str, perm_codes: tuple[str, ...]) -> None:
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

    # HR roles: can view admin list + team (calendar/reporting).
    _grant(
        "HR_ADMIN",
        (
            "attendance:correction:read",
            "attendance:team:read",
            "attendance:admin:read",
        ),
    )
    _grant(
        "HR_MANAGER",
        (
            "attendance:correction:read",
            "attendance:team:read",
            "attendance:admin:read",
        ),
    )

    # Managers: team visibility.
    _grant("MANAGER", ("attendance:team:read",))

    # Employees: ESS submit/read.
    _grant(
        "EMPLOYEE",
        (
            "attendance:correction:submit",
            "attendance:correction:read",
        ),
    )

    # Seed workflow request type used by attendance corrections.
    op.execute(
        sa.text(
            """
            INSERT INTO workflow.request_types (code, name, description)
            VALUES (
              'ATTENDANCE_CORRECTION',
              'Attendance correction',
              'Employee attendance regularization request (ESS)'
            )
            ON CONFLICT (code) DO NOTHING
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
              AND r.code IN ('ADMIN','HR_ADMIN','HR_MANAGER','MANAGER','EMPLOYEE')
              AND p.code IN ({quoted})
            """
        )
    )
    op.execute(sa.text(f"DELETE FROM iam.permissions WHERE code IN ({quoted})"))
    op.execute(sa.text("DELETE FROM workflow.request_types WHERE code = 'ATTENDANCE_CORRECTION'"))

