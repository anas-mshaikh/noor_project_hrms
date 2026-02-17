"""IAM: refresh token storage for JWT auth.

Revision ID: 85a23039697f
Revises: 78a23d4f40ba
Create Date: 2026-02-01

Security model:
- Access tokens are short-lived JWTs.
- Refresh tokens are random secrets returned once to the client.
- We store ONLY a hash of the refresh token (never the raw token).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "85a23039697f"
down_revision = "78a23d4f40ba"
branch_labels = None
depends_on = None


UUID = postgresql.UUID


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["iam.users.id"],
            name="fk_refresh_tokens_user_id",
            ondelete="CASCADE",
        ),
        schema="iam",
    )

    op.create_index(
        "ix_refresh_tokens_user_id",
        "refresh_tokens",
        ["user_id"],
        unique=False,
        schema="iam",
    )
    op.create_index(
        "uq_refresh_tokens_token_hash",
        "refresh_tokens",
        ["token_hash"],
        unique=True,
        schema="iam",
    )


def downgrade() -> None:
    op.drop_index("uq_refresh_tokens_token_hash", table_name="refresh_tokens", schema="iam")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens", schema="iam")
    op.drop_table("refresh_tokens", schema="iam")

