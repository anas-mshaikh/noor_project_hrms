"""Workflow v1: seed workflow permissions + request type.

Revision ID: f6c2951ba7d5
Revises: afa169e50ce8
Create Date: 2026-02-16

Milestone 2 adds a reusable workflow approvals engine. This migration seeds:
- colon-style workflow permissions used by require_permission(...)
- minimal DMS file read/write permissions for workflow attachments
- request_types.HR_PROFILE_CHANGE (for workflow engine tests and future modules)

Notes:
- Additive and idempotent (safe for dev resets).
- Existing uppercase permission codes remain in the DB.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "f6c2951ba7d5"
down_revision = "afa169e50ce8"
branch_labels = None
depends_on = None


PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("workflow:request:submit", "Submit workflow requests"),
    ("workflow:request:read", "Read workflow requests"),
    ("workflow:request:approve", "Approve/reject workflow requests"),
    ("workflow:request:admin", "Admin access to workflow requests"),
    ("workflow:definition:read", "Read workflow definitions"),
    ("workflow:definition:write", "Write workflow definitions"),
    ("dms:file:read", "Read DMS files"),
    ("dms:file:write", "Write DMS files"),
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

    _grant(
        "ADMIN",
        tuple(code for code, _desc in PERMISSIONS),
    )

    # HR roles: HR_ADMIN can manage definitions; HR_MANAGER can read.
    _grant(
        "HR_ADMIN",
        (
            "workflow:request:submit",
            "workflow:request:read",
            "workflow:request:approve",
            "workflow:request:admin",
            "workflow:definition:read",
            "workflow:definition:write",
            "dms:file:read",
        ),
    )
    _grant(
        "HR_MANAGER",
        (
            "workflow:request:submit",
            "workflow:request:read",
            "workflow:request:approve",
            "workflow:request:admin",
            "workflow:definition:read",
            "dms:file:read",
        ),
    )

    _grant(
        "MANAGER",
        (
            "workflow:request:read",
            "workflow:request:approve",
            "dms:file:read",
        ),
    )
    _grant(
        "EMPLOYEE",
        (
            "workflow:request:submit",
            "workflow:request:read",
            "dms:file:read",
        ),
    )

    # Request type used by workflow engine tests (and future HR modules).
    op.execute(
        sa.text(
            """
            INSERT INTO workflow.request_types (code, name, description)
            VALUES ('HR_PROFILE_CHANGE', 'HR Profile Change', 'Employee profile change request')
            ON CONFLICT (code) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    # Best-effort cleanup (dev only).
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
    op.execute(sa.text("DELETE FROM workflow.request_types WHERE code = 'HR_PROFILE_CHANGE'"))

