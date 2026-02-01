"""IAM: seed HR_ADMIN role (required for enterprise RBAC).

Revision ID: 9f2b3c4d5e6f
Revises: 85a23039697f
Create Date: 2026-02-01

Why:
- DB vNext 0002 seeded ADMIN/HR_MANAGER/MANAGER/EMPLOYEE.
- Enterprise IAM flows also require HR_ADMIN for elevated HR operations.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "9f2b3c4d5e6f"
down_revision = "85a23039697f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO iam.roles (code, name, description)
            VALUES ('HR_ADMIN', 'HR Administrator', 'Elevated HR access within a scope')
            ON CONFLICT (code) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM iam.roles WHERE code = 'HR_ADMIN'"))

