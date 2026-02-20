"""
Tenancy factories for tests.

These factories seed minimal tenant/company/branch hierarchy for tests.

Implementation note:
- We use the existing SQL seed helper (fast, deterministic).
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from tests.helpers.seed import seed_tenant_company


def seed_minimal_tenant(engine: Engine) -> dict[str, str]:
    """
    Seed a minimal tenant/company/branch hierarchy.

    Returns a dict with:
      tenant_id, company_id, branch_id (as strings).
    """

    return seed_tenant_company(engine)

