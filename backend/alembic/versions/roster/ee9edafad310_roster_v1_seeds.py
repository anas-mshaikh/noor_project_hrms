"""Roster v1 + payable summaries: seed permissions.

Revision ID: ee9edafad310
Revises: e97254580575
Create Date: 2026-02-20

This migration seeds:
- roster permission vocabulary (shift templates, assignments, overrides, defaults)
- payable summary permission vocabulary (self/team/admin read + recompute trigger)
- default role mappings for v1

Notes:
- We use idempotent inserts (`ON CONFLICT DO NOTHING`) to keep environments
  consistent across re-deploys.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "ee9edafad310"
down_revision = "e97254580575"
branch_labels = None
depends_on = None


PERMISSIONS: tuple[tuple[str, str], ...] = (
    # Roster
    ("roster:shift:read", "Read shift templates"),
    ("roster:shift:write", "Write shift templates"),
    ("roster:assignment:read", "Read shift assignments"),
    ("roster:assignment:write", "Write shift assignments"),
    ("roster:override:read", "Read roster overrides"),
    ("roster:override:write", "Write roster overrides"),
    ("roster:defaults:write", "Write branch default roster settings"),
    # Payable summaries
    ("attendance:payable:read", "Read own payable day summaries (ESS)"),
    ("attendance:payable:team:read", "Read team payable day summaries (MSS)"),
    ("attendance:payable:admin:read", "Read payable day summaries (HR/admin)"),
    ("attendance:payable:recompute", "Recompute payable day summaries"),
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

    roster_all = (
        "roster:shift:read",
        "roster:shift:write",
        "roster:assignment:read",
        "roster:assignment:write",
        "roster:override:read",
        "roster:override:write",
        "roster:defaults:write",
    )
    payable_admin = (
        "attendance:payable:admin:read",
        "attendance:payable:recompute",
    )

    # ADMIN: full access (roster + payable).
    _grant("ADMIN", tuple(code for code, _desc in PERMISSIONS))

    # HR_ADMIN: roster administration + payable reporting/recompute.
    _grant("HR_ADMIN", roster_all + payable_admin)

    # MANAGER: team payable read.
    _grant("MANAGER", ("attendance:payable:team:read",))

    # EMPLOYEE: self payable read.
    _grant("EMPLOYEE", ("attendance:payable:read",))


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
              AND r.code IN ('ADMIN','HR_ADMIN','MANAGER','EMPLOYEE')
              AND p.code IN ({quoted})
            """
        )
    )
    op.execute(sa.text(f"DELETE FROM iam.permissions WHERE code IN ({quoted})"))

