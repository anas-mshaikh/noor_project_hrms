"""IAM: seed colon-style permission codes and map to seeded roles.

Revision ID: 6e4f83bf4ad6
Revises: 9f2b3c4d5e6f
Create Date: 2026-02-12

Milestone 1 introduces permission-driven RBAC with colon-style codes in the
application layer (e.g. `iam:user:read`). This migration seeds those codes into
`iam.permissions` and maps them to the built-in roles.

Notes:
- Additive only; existing uppercase permission codes remain in the DB.
- Role permissions are inserted idempotently (PK is (role_id, permission_id)).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "6e4f83bf4ad6"
down_revision = "9f2b3c4d5e6f"
branch_labels = None
depends_on = None


PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("tenancy:read", "Read tenant masters"),
    ("tenancy:write", "Write tenant masters"),
    ("iam:user:read", "Read IAM users"),
    ("iam:user:write", "Write IAM users"),
    ("iam:role:assign", "Assign IAM roles"),
    ("iam:permission:read", "Read IAM permissions"),
    ("hr:employee:read", "Read HR employees"),
    ("hr:employee:write", "Write HR employees"),
    ("hr:team:read", "Read manager team views"),
    ("ess:profile:read", "Read ESS profile"),
    ("ess:profile:write", "Write ESS profile"),
    ("notifications:read", "Read in-app notifications"),
    ("vision:camera:read", "Read cameras"),
    ("vision:camera:write", "Write cameras"),
    ("vision:video:upload", "Upload videos"),
    ("vision:job:run", "Run processing jobs"),
    ("vision:results:read", "Read processing results"),
    ("face:library:read", "Read face library"),
    ("face:library:write", "Write face library"),
    ("face:recognize", "Run face recognition"),
    ("work:task:read", "Read tasks"),
    ("work:task:write", "Write tasks"),
    ("work:task:auto_assign", "Auto-assign tasks"),
    ("imports:read", "Read imports"),
    ("imports:write", "Write imports"),
    ("mobile:sync", "Run mobile sync"),
    ("mobile:accounts:read", "Read mobile accounts"),
    ("mobile:accounts:write", "Write mobile accounts"),
    ("hr:recruiting:read", "Read recruiting pipeline"),
    ("hr:recruiting:write", "Write recruiting pipeline"),
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

    _grant("ADMIN", all_codes)

    # HR roles: can operate HR masters and read tenancy context.
    _grant(
        "HR_ADMIN",
        (
            "tenancy:read",
            "iam:user:read",
            "hr:employee:read",
            "hr:employee:write",
            "hr:team:read",
            "ess:profile:read",
            "ess:profile:write",
            "notifications:read",
            "hr:recruiting:read",
            "hr:recruiting:write",
        ),
    )
    _grant(
        "HR_MANAGER",
        (
            "tenancy:read",
            "hr:employee:read",
            "hr:employee:write",
            "hr:team:read",
            "ess:profile:read",
            "ess:profile:write",
            "notifications:read",
            "hr:recruiting:read",
            "hr:recruiting:write",
        ),
    )

    # Managers can access MSS team views; also have ESS profile access.
    _grant(
        "MANAGER",
        (
            "hr:team:read",
            "ess:profile:read",
            "ess:profile:write",
            "notifications:read",
        ),
    )

    # Employees can access ESS profile + notifications.
    _grant(
        "EMPLOYEE",
        (
            "ess:profile:read",
            "ess:profile:write",
            "notifications:read",
        ),
    )


def downgrade() -> None:
    # Best-effort cleanup (dev only). We only delete mappings for the codes we inserted.
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

