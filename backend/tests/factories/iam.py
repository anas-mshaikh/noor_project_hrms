"""
IAM factories for tests.

These factories seed IAM users with scoped role assignments.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from tests.helpers.seed import seed_user


def seed_scoped_user(
    engine: Engine,
    *,
    tenant_id: str,
    company_id: str,
    branch_id: str,
    role_code: str,
    email_prefix: str | None = None,
) -> dict[str, str]:
    """Seed an IAM user with a scoped role assignment."""

    return seed_user(
        engine,
        tenant_id=tenant_id,
        company_id=company_id,
        branch_id=branch_id,
        role_code=role_code,
        email_prefix=email_prefix,
    )
