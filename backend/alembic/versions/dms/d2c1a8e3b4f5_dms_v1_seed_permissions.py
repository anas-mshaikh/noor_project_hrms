"""DMS v1: seed permissions for document library + expiry.

Revision ID: d2c1a8e3b4f5
Revises: d1c0a7e2b3f4
Create Date: 2026-02-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "d2c1a8e3b4f5"
down_revision = "d1c0a7e2b3f4"
branch_labels = None
depends_on = None


PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("dms:document-type:read", "Read DMS document types"),
    ("dms:document-type:write", "Write DMS document types"),
    ("dms:document:read", "Read DMS documents"),
    ("dms:document:write", "Write DMS documents"),
    ("dms:document:verify", "Submit/approve DMS document verification workflows"),
    ("dms:expiry:read", "Read DMS expiry rules/reports"),
    ("dms:expiry:write", "Write DMS expiry rules"),
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
    """
    Grant a list of permission codes to a role code.

    This is idempotent due to the unique constraint on (role_id, permission_id).
    """

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

    # HR_ADMIN: manage document library + expiry rules.
    _grant(
        "HR_ADMIN",
        (
            "dms:document-type:read",
            "dms:document-type:write",
            "dms:document:read",
            "dms:document:write",
            "dms:document:verify",
            "dms:expiry:read",
            "dms:expiry:write",
            "dms:file:read",
            "dms:file:write",
        ),
    )

    # HR_MANAGER: read docs + expiry reports (write can be added later).
    _grant(
        "HR_MANAGER",
        (
            "dms:document-type:read",
            "dms:document:read",
            "dms:expiry:read",
            "dms:file:read",
        ),
    )

    # EMPLOYEE: read own docs; upload/read own files for evidence.
    _grant(
        "EMPLOYEE",
        (
            "dms:document:read",
            "dms:file:read",
            "dms:file:write",
        ),
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

