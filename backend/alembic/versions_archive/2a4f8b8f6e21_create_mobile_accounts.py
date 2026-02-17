"""create mobile_accounts

Revision ID: 2a4f8b8f6e21
Revises: e3c5f2b1a6d7
Create Date: 2026-01-19

This table is the Postgres source-of-truth for the mobile login bootstrap mapping:
  Firebase Auth uid -> org/store/employee identity.

Firestore `users/{uid}` docs are a *derived cache* written by the backend.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2a4f8b8f6e21"
down_revision = "e3c5f2b1a6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # We use gen_random_uuid() for PK defaults; this lives in the pgcrypto extension.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "mobile_accounts",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            sa.UUID(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "store_id",
            sa.UUID(),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            sa.UUID(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Denormalized employee_code for readability and audit logs.
        sa.Column("employee_code", sa.String(length=64), nullable=False),
        # Firebase Auth user id (uid).
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column(
            "role",
            sa.String(length=32),
            server_default="employee",
            nullable=False,
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "store_id",
            "employee_id",
            name="uq_mobile_accounts_store_employee",
        ),
        sa.UniqueConstraint("firebase_uid", name="uq_mobile_accounts_firebase_uid"),
    )

    op.create_index(
        "ix_mobile_accounts_store_active",
        "mobile_accounts",
        ["store_id", "active"],
    )
    op.create_index(
        "ix_mobile_accounts_employee_id",
        "mobile_accounts",
        ["employee_id"],
    )
    op.create_index(
        "ix_mobile_accounts_org_id",
        "mobile_accounts",
        ["org_id"],
    )
    op.create_index(
        "ix_mobile_accounts_store_id",
        "mobile_accounts",
        ["store_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_mobile_accounts_store_id", table_name="mobile_accounts")
    op.drop_index("ix_mobile_accounts_org_id", table_name="mobile_accounts")
    op.drop_index("ix_mobile_accounts_employee_id", table_name="mobile_accounts")
    op.drop_index("ix_mobile_accounts_store_active", table_name="mobile_accounts")
    op.drop_table("mobile_accounts")

