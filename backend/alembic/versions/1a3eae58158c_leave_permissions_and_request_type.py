"""Leave v1: seed permissions and workflow request type.

Revision ID: 1a3eae58158c
Revises: a0793d36f998
Create Date: 2026-02-16

Milestone 3 introduces Leave Management. This migration seeds:
- colon-style leave permissions (RBAC)
- workflow.request_types.LEAVE_REQUEST (for approvals via workflow engine)

Notes:
- Additive and idempotent.
- Existing permission codes remain in the DB.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "1a3eae58158c"
down_revision = "a0793d36f998"
branch_labels = None
depends_on = None


PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("leave:type:read", "Read leave types"),
    ("leave:type:write", "Write leave types"),
    ("leave:policy:read", "Read leave policies"),
    ("leave:policy:write", "Write leave policies"),
    ("leave:allocation:write", "Allocate/adjust leave balances"),
    ("leave:balance:read", "Read leave balances"),
    ("leave:request:submit", "Submit leave requests"),
    ("leave:request:read", "Read leave requests"),
    ("leave:team:read", "Read team leave calendar"),
    ("leave:admin:read", "Read leave admin reports"),
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

    # HR roles: can configure and allocate.
    _grant(
        "HR_ADMIN",
        (
            "leave:type:read",
            "leave:type:write",
            "leave:policy:read",
            "leave:policy:write",
            "leave:allocation:write",
            "leave:balance:read",
            "leave:request:read",
            "leave:team:read",
            "leave:admin:read",
        ),
    )
    _grant(
        "HR_MANAGER",
        (
            "leave:type:read",
            "leave:type:write",
            "leave:policy:read",
            "leave:policy:write",
            "leave:allocation:write",
            "leave:balance:read",
            "leave:request:read",
            "leave:team:read",
            "leave:admin:read",
        ),
    )

    # Managers: can view team calendar.
    _grant(
        "MANAGER",
        (
            "leave:balance:read",
            "leave:request:read",
            "leave:team:read",
        ),
    )

    # Employees: ESS submit/read + balances.
    _grant(
        "EMPLOYEE",
        (
            "leave:type:read",
            "leave:balance:read",
            "leave:request:submit",
            "leave:request:read",
        ),
    )

    # Seed workflow request type used by Leave approvals.
    op.execute(
        sa.text(
            """
            INSERT INTO workflow.request_types (code, name, description)
            VALUES ('LEAVE_REQUEST', 'Leave request', 'Employee leave request (ESS)')
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

    # Best-effort cleanup (dev only).
    op.execute(sa.text("DELETE FROM workflow.request_types WHERE code = 'LEAVE_REQUEST'"))

