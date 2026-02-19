"""Onboarding v2 + profile change v1: seed permissions and request type safety.

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-02-19

This migration seeds:
- permission vocabulary for onboarding v2 + HR profile change v1
- default role mappings (ADMIN/HR_ADMIN/EMPLOYEE)
- workflow.request_types safety insert for HR_PROFILE_CHANGE (baseline already
  seeds it, but this keeps environments consistent)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("onboarding:template:read", "Read onboarding plan templates"),
    ("onboarding:template:write", "Write onboarding plan templates"),
    ("onboarding:bundle:read", "Read onboarding bundles"),
    ("onboarding:bundle:write", "Write onboarding bundles"),
    ("onboarding:task:read", "Read onboarding tasks"),
    ("onboarding:task:submit", "Submit onboarding tasks (ESS)"),
    ("hr:profile-change:submit", "Submit HR profile change requests (ESS)"),
    ("hr:profile-change:read", "Read HR profile change requests"),
    (
        "hr:profile-change:apply",
        "Apply HR profile change requests (terminal workflow hook)",
    ),
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

    # HR_ADMIN: manage onboarding templates/bundles and view/apply profile changes.
    _grant(
        "HR_ADMIN",
        (
            "onboarding:template:read",
            "onboarding:template:write",
            "onboarding:bundle:read",
            "onboarding:bundle:write",
            "onboarding:task:read",
            "hr:profile-change:read",
            "hr:profile-change:apply",
        ),
    )

    # EMPLOYEE: ESS visibility + submit.
    _grant(
        "EMPLOYEE",
        (
            "onboarding:bundle:read",
            "onboarding:task:read",
            "onboarding:task:submit",
            "hr:profile-change:submit",
            "hr:profile-change:read",
        ),
    )

    # Workflow request type safety insert (baseline already seeds this).
    op.execute(
        sa.text(
            """
            INSERT INTO workflow.request_types (code, name, description)
            VALUES (
              'HR_PROFILE_CHANGE',
              'HR Profile Change',
              'Employee profile change request'
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
              AND r.code IN ('ADMIN','HR_ADMIN','EMPLOYEE')
              AND p.code IN ({quoted})
            """
        )
    )
    op.execute(sa.text(f"DELETE FROM iam.permissions WHERE code IN ({quoted})"))
