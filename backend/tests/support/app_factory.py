"""
Test app factory helpers.

This module wraps the existing `tests.helpers.app.make_app` helper to keep the
new test infrastructure (support/ + factories/) self-contained.

We keep it intentionally small:
- production app creation is handled elsewhere
- tests should explicitly include only the routers they need for speed
"""

from __future__ import annotations

from typing import Sequence

from fastapi.testclient import TestClient

from tests.helpers.app import make_app


def make_test_client(*router_modules: str, prefix: str = "/api/v1") -> TestClient:
    """Create a TestClient for a minimal router set."""

    return TestClient(make_app(*router_modules, prefix=prefix))


def make_test_client_from_list(router_modules: Sequence[str], *, prefix: str = "/api/v1") -> TestClient:
    """Create a TestClient for a router list (convenient for parameterized tests)."""

    return make_test_client(*router_modules, prefix=prefix)

