"""
DMS factories for tests.

These helpers create document types and upload test files via the DMS API.
"""

from __future__ import annotations

from tests.support.api_client import ApiClient


def create_document_type(
    api: ApiClient,
    *,
    code: str,
    name: str,
    requires_expiry: bool = False,
    is_active: bool = True,
) -> str:
    """Create a DMS document type and return its id."""

    dt = api.post(
        "/api/v1/dms/document-types",
        json={
            "code": code,
            "name": name,
            "requires_expiry": bool(requires_expiry),
            "is_active": bool(is_active),
        },
    )
    return str(dt["id"])
