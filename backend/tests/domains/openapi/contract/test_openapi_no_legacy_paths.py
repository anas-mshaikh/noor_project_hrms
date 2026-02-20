from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping API integration tests",
)


def test_openapi_has_no_legacy_stores_or_orgs() -> None:
    """
    Smoke-test that the full FastAPI app boots and legacy master routes are removed.
    """
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    r = client.get("/openapi.json")
    assert r.status_code == 200, r.text

    paths = set((r.json() or {}).get("paths", {}).keys())
    assert not any(p.startswith("/api/v1/stores") for p in paths)
    assert not any(p.startswith("/api/v1/organizations") for p in paths)

