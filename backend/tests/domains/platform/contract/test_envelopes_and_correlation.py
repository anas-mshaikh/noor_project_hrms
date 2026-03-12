from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine

from tests.helpers.app import make_app
from tests.helpers.seed import cleanup, seed_tenant_company, seed_user
from tests.support.httpx_client import asgi_client, expect_error, expect_ok


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.contract,
    pytest.mark.api,
    pytest.mark.skipif(
        not os.getenv("DATABASE_URL"),
        reason="DATABASE_URL not set; skipping API integration tests",
    ),
]


async def _login(client, *, email: str, password: str) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return expect_ok(response)


def _engine():
    return create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


async def test_health_success_envelope_and_correlation_header() -> None:
    app = make_app("app.api.v1.health")
    async with asgi_client(app) as client:
        response = await client.get("/api/v1/health")

    data = expect_ok(response)
    assert data == {"status": "ok"}
    assert response.headers["x-correlation-id"]


async def test_auth_me_error_includes_correlation_id_header_and_payload() -> None:
    app = make_app("app.auth.router")
    async with asgi_client(app) as client:
        response = await client.get("/api/v1/auth/me")

    err = expect_error(response)
    assert response.status_code == 401
    assert err["code"] == "unauthorized"
    assert err["correlation_id"] == response.headers["x-correlation-id"]


async def test_dms_file_download_stays_raw_on_success_and_enveloped_on_failure() -> None:
    engine = _engine()
    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="contract-dms-admin",
    )

    app = make_app("app.auth.router", "app.domains.dms.router_files")

    try:
        async with asgi_client(app) as client:
            login_data = await _login(client, email=admin["email"], password=admin["password"])
            token = login_data["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            upload = await client.post(
                "/api/v1/dms/files",
                headers=headers,
                files={"file": ("hello.txt", b"hello-dms", "text/plain")},
            )
            file_id = expect_ok(upload)["id"]

            download = await client.get(f"/api/v1/dms/files/{file_id}/download", headers=headers)
            assert download.status_code == 200
            assert download.content == b"hello-dms"
            assert download.headers["x-correlation-id"]
            assert download.headers.get("content-type", "").startswith("text/plain")

            missing = await client.get(f"/api/v1/dms/files/{uuid.uuid4()}/download", headers=headers)
            err = expect_error(missing)
            assert missing.status_code == 404
            assert err["code"] == "dms.file.not_found"
            assert err["correlation_id"] == missing.headers["x-correlation-id"]
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"]])


async def test_readyz_is_enveloped_and_reports_current_revision() -> None:
    app = make_app("app.api.v1.health")
    async with asgi_client(app) as client:
        response = await client.get("/api/v1/readyz")

    data = expect_ok(response)
    assert data["status"] == "ready"
    assert data["revision"]
    assert response.headers["x-correlation-id"]
