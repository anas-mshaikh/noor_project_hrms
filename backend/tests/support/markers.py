"""
Marker constants (optional).

Pytest markers are registered in tests/pytest.ini.

These constants are purely a readability helper for large suites where marker
strings become noisy. Using them is optional.
"""

from __future__ import annotations


UNIT = "unit"
INTEGRATION = "integration"
API = "api"
CONTRACT = "contract"
E2E = "e2e"
SLOW = "slow"
TENANT = "tenant"
RBAC = "rbac"
