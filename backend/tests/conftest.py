"""
Global pytest fixtures for backend tests.

Goals:
- Keep test setup consistent and DRY.
- Enforce tenant/RBAC patterns via reusable builders.
- Keep tests deterministic and CI-friendly.

Note on isolation:
- API tests often commit database transactions through the app session.
- For API tests, rollback-based fixtures are insufficient.
- This file provides a cleanup registry that deletes seeded tenants/users at
  the end of the test (deterministic and safe via FK cascades).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Iterator, Sequence

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from tests.helpers.app import make_app
from tests.helpers.http import login
from tests.helpers.seed import cleanup, seed_tenant_company, seed_user


@dataclass(frozen=True)
class TenantIds:
    """Tenant/company/branch ids used across API and DB seed helpers."""

    tenant_id: str
    company_id: str
    branch_id: str


@dataclass(frozen=True)
class SeededUser:
    """Seeded IAM user with role assignment (used for login)."""

    user_id: str
    email: str
    password: str
    role_code: str


@dataclass(frozen=True)
class ApiActor:
    """Authenticated actor convenience wrapper."""

    user: SeededUser
    token: str
    tenant: TenantIds

    def headers(self) -> dict[str, str]:
        """
        Build auth + scope headers.

        We include explicit scope headers to avoid tests accidentally depending
        on implicit "first allowed company/branch" selection.
        """

        return {
            "Authorization": f"Bearer {self.token}",
            "X-Tenant-Id": self.tenant.tenant_id,
            "X-Company-Id": self.tenant.company_id,
            "X-Branch-Id": self.tenant.branch_id,
        }


class CleanupRegistry:
    """
    Tracks seeded tenants/users and cleans them up after each test.

    Why:
    - API tests create committed rows; transaction rollbacks won't clean them.
    - Deleting the tenant row is deterministic and cascades across tenancy-scoped
      records.
    - Users are global (`iam.users`) so we delete them explicitly.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._tenant_ids: set[str] = set()
        self._user_ids: list[str] = []

    def track_tenant(self, tenant_id: str) -> None:
        """Register a tenant for post-test cleanup."""

        self._tenant_ids.add(tenant_id)

    def track_user(self, user_id: str) -> None:
        """Register a global user for post-test cleanup."""

        self._user_ids.append(user_id)

    def finalize(self) -> None:
        """Delete tracked tenants and users."""

        for tenant_id in list(self._tenant_ids):
            cleanup(self._engine, tenant_id=tenant_id, user_ids=[])
        if self._user_ids:
            cleanup(self._engine, tenant_id=None, user_ids=self._user_ids)


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """
    Session-scoped SQLAlchemy Engine for DB seeding and direct DB assertions.

    Notes:
    - API tests still run through the app’s DB session dependency.
    - We use this engine for deterministic seed/cleanup and DB assertions.
    """

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set; skipping integration/API tests")

    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def cleanup_registry(db_engine: Engine) -> Iterator[CleanupRegistry]:
    """
    Per-test cleanup registry.

    Any factory that seeds tenants/users should register them here so tests
    don’t need noisy try/finally blocks.
    """

    reg = CleanupRegistry(db_engine)
    yield reg
    reg.finalize()


@pytest.fixture()
def tenant_factory(
    db_engine: Engine, cleanup_registry: CleanupRegistry
) -> Callable[[], TenantIds]:
    """Factory that creates a tenant/company/branch and registers for cleanup."""

    def _create() -> TenantIds:
        t = seed_tenant_company(db_engine)
        cleanup_registry.track_tenant(t["tenant_id"])
        return TenantIds(
            tenant_id=t["tenant_id"],
            company_id=t["company_id"],
            branch_id=t["branch_id"],
        )

    return _create


@pytest.fixture()
def user_factory(
    db_engine: Engine, cleanup_registry: CleanupRegistry
) -> Callable[[TenantIds, str], SeededUser]:
    """Factory that creates an IAM user for a tenant and registers for cleanup."""

    def _create(tenant: TenantIds, role_code: str) -> SeededUser:
        u = seed_user(
            db_engine,
            tenant_id=tenant.tenant_id,
            company_id=tenant.company_id,
            branch_id=tenant.branch_id,
            role_code=role_code,
        )
        cleanup_registry.track_user(u["user_id"])
        return SeededUser(
            user_id=u["user_id"],
            email=u["email"],
            password=u["password"],
            role_code=role_code,
        )

    return _create


@pytest.fixture()
def client_factory() -> Callable[[Sequence[str]], TestClient]:
    """
    Factory for TestClient with an explicit router set.

    Recommended usage:
    - API tests include only the routers they need (faster imports).
    - Contract tests may include the full API router.
    """

    def _make(router_modules: Sequence[str]) -> TestClient:
        return TestClient(make_app(*router_modules))

    return _make


@pytest.fixture()
def actor_factory(user_factory) -> Callable[[TestClient, TenantIds, str], ApiActor]:
    """Creates a seeded user + logs them in -> ApiActor."""

    def _make(client: TestClient, tenant: TenantIds, role_code: str) -> ApiActor:
        user = user_factory(tenant, role_code)
        token = login(client, email=user.email, password=user.password)["access_token"]
        return ApiActor(user=user, token=token, tenant=tenant)

    return _make


@pytest.fixture()
def db_session(db_engine: Engine) -> Iterator[Session]:
    """
    DB integration fixture (transaction + rollback).

    Use this ONLY for *integration* tests that call services directly (no HTTP).
    Do not use this fixture for API tests, since API requests use independent
    sessions and commits.
    """

    connection = db_engine.connect()
    txn = connection.begin()
    session_local = sessionmaker(
        bind=connection, autoflush=False, expire_on_commit=False
    )
    session = session_local()

    try:
        yield session
    finally:
        session.close()
        txn.rollback()
        connection.close()
