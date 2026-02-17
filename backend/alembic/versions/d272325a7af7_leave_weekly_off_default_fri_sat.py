"""Leave v1: default weekly_off to Fri+Sat for new branches.

Revision ID: d272325a7af7
Revises: 1a3eae58158c
Create Date: 2026-02-17

We require weekly off configuration (7 weekdays) per branch for leave submission.
This migration:
- Backfills missing weekly_off rows for existing branches (idempotent).
- Adds an AFTER INSERT trigger on tenancy.branches to auto-initialize weekly_off
  for new branches with Saudi-default weekend: Friday+Saturday.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "d272325a7af7"
down_revision = "1a3eae58158c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill: ensure every branch has 7 weekday rows. Do not override existing values.
    op.execute(
        sa.text(
            """
            INSERT INTO leave.weekly_off (tenant_id, branch_id, weekday, is_off)
            SELECT
              b.tenant_id,
              b.id AS branch_id,
              gs.weekday,
              (gs.weekday IN (4,5)) AS is_off
            FROM tenancy.branches b
            CROSS JOIN (SELECT generate_series(0,6) AS weekday) gs
            ON CONFLICT (tenant_id, branch_id, weekday) DO NOTHING
            """
        )
    )

    # Trigger to initialize future branches with Fri/Sat off.
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION leave.init_weekly_off_for_branch()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
              INSERT INTO leave.weekly_off (tenant_id, branch_id, weekday, is_off)
              SELECT
                NEW.tenant_id,
                NEW.id,
                gs.weekday,
                (gs.weekday IN (4,5)) AS is_off
              FROM (SELECT generate_series(0,6) AS weekday) gs
              ON CONFLICT (tenant_id, branch_id, weekday) DO NOTHING;

              RETURN NEW;
            END;
            $$;
            """
        )
    )

    op.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS trg_leave_weekly_off_default ON tenancy.branches;
            CREATE TRIGGER trg_leave_weekly_off_default
            AFTER INSERT ON tenancy.branches
            FOR EACH ROW
            EXECUTE FUNCTION leave.init_weekly_off_for_branch();
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_leave_weekly_off_default ON tenancy.branches;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS leave.init_weekly_off_for_branch();"))

