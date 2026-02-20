"""
Workflow factories for tests.

This module provides reusable helpers to create deterministic workflow
definitions for a request_type_code:
- MANAGER step only
- ROLE(role_code) step only

Why factories:
- Keeps test bodies focused on business intent (AAA).
- Avoids copy-pasting definition/step/activate boilerplate across domains.
"""

from __future__ import annotations

import uuid

from tests.support.api_client import ApiClient


def create_definition_manager_only(
    api: ApiClient,
    *,
    request_type_code: str,
    code_prefix: str,
) -> str:
    """
    Create and activate a single-step MANAGER workflow definition.

    Returns:
      workflow definition id (uuid string).
    """

    definition = api.post(
        "/api/v1/workflow/definitions",
        json={
            "request_type_code": request_type_code,
            "code": f"{code_prefix}_{uuid.uuid4().hex[:6]}",
            "name": f"{request_type_code} (Manager only)",
            "version": 1,
        },
    )
    definition_id = definition["id"]

    api.post(
        f"/api/v1/workflow/definitions/{definition_id}/steps",
        json={"steps": [{"step_index": 0, "assignee_type": "MANAGER"}]},
    )
    api.post(f"/api/v1/workflow/definitions/{definition_id}/activate", json={})
    return str(definition_id)


def create_definition_role(
    api: ApiClient,
    *,
    request_type_code: str,
    role_code: str,
    code_prefix: str,
) -> str:
    """
    Create and activate a single-step ROLE workflow definition.

    Returns:
      workflow definition id (uuid string).
    """

    definition = api.post(
        "/api/v1/workflow/definitions",
        json={
            "request_type_code": request_type_code,
            "code": f"{code_prefix}_{uuid.uuid4().hex[:6]}",
            "name": f"{request_type_code} (Role {role_code})",
            "version": 1,
        },
    )
    definition_id = definition["id"]

    api.post(
        f"/api/v1/workflow/definitions/{definition_id}/steps",
        json={
            "steps": [
                {"step_index": 0, "assignee_type": "ROLE", "assignee_role_code": role_code}
            ]
        },
    )
    api.post(f"/api/v1/workflow/definitions/{definition_id}/activate", json={})
    return str(definition_id)

