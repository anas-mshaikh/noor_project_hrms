from __future__ import annotations

import uuid

import pytest

from tests.support.api_client import ApiClient


pytestmark = [pytest.mark.api, pytest.mark.tenant, pytest.mark.rbac]


def test_shift_template_create_and_compute_minutes(
    client_factory,
    tenant_factory,
    actor_factory,
) -> None:
    # Arrange
    client = client_factory(
        [
            "app.auth.router",
            "app.domains.roster.router",
        ]
    )
    tenant = tenant_factory()
    admin = actor_factory(client, tenant, "ADMIN")
    api = ApiClient(client=client, headers=admin.headers())

    # Act: normal shift
    created = api.post(
        f"/api/v1/roster/branches/{tenant.branch_id}/shifts",
        json={
            "code": f"DAY_{uuid.uuid4().hex[:6].upper()}",
            "name": "Day Shift",
            "start_time": "09:00",
            "end_time": "18:00",
            "break_minutes": 60,
        },
    )

    # Assert
    assert int(created["expected_minutes"]) == 480

    # Act: overnight shift (end wraps to next day)
    overnight = api.post(
        f"/api/v1/roster/branches/{tenant.branch_id}/shifts",
        json={
            "code": f"NIGHT_{uuid.uuid4().hex[:6].upper()}",
            "name": "Night Shift",
            "start_time": "22:00",
            "end_time": "06:00",
            "break_minutes": 30,
        },
    )

    # Assert
    assert int(overnight["expected_minutes"]) == 450

