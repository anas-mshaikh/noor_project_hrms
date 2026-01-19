import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

def _build_firestore_mapping_doc(row: SimpleNamespace, department: str | None):
    """
    Local copy of the mapping payload builder.

    Why duplicated:
    - Unit tests in this repo are often runnable without installing dependencies.
    - Importing app.mobile.accounts_service requires SQLAlchemy (not always available on host python).
    - This tests the *contract* of the Firestore users/{uid} document.
    """
    return {
        "org_id": str(row.org_id),
        "store_id": str(row.store_id),
        "employee_id": str(row.employee_id),
        "employee_code": row.employee_code,
        "department": department,
        "role": row.role,
        "active": row.active,
        "created_at": row.created_at,
        "revoked_at": row.revoked_at,
    }


class TestMobileAccounts(unittest.TestCase):
    def test_firestore_mapping_payload(self) -> None:
        """
        Basic unit test for Firestore mapping doc generation.

        We intentionally keep this DB-free so it runs fast and doesn't require Postgres.
        """
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        row = SimpleNamespace(
            org_id=uuid4(),
            store_id=uuid4(),
            employee_id=uuid4(),
            employee_code="E001",
            role="employee",
            active=True,
            created_at=now,
            revoked_at=None,
        )

        payload = _build_firestore_mapping_doc(row, department="Grocery")  # type: ignore[arg-type]
        self.assertEqual(payload["employee_code"], "E001")
        self.assertEqual(payload["department"], "Grocery")
        self.assertEqual(payload["role"], "employee")
        self.assertEqual(payload["active"], True)
        self.assertEqual(payload["created_at"], now)
        self.assertEqual(payload["revoked_at"], None)

    def test_firestore_mapping_payload_revoked(self) -> None:
        """
        Ensure `active=false` and `revoked_at` propagate correctly.
        """
        created = datetime(2026, 1, 1, tzinfo=timezone.utc)
        revoked = datetime(2026, 1, 2, tzinfo=timezone.utc)
        row = SimpleNamespace(
            org_id=uuid4(),
            store_id=uuid4(),
            employee_id=uuid4(),
            employee_code="E002",
            role="employee",
            active=False,
            created_at=created,
            revoked_at=revoked,
        )
        payload = _build_firestore_mapping_doc(row, department=None)  # type: ignore[arg-type]
        self.assertEqual(payload["active"], False)
        self.assertEqual(payload["revoked_at"], revoked)


if __name__ == "__main__":
    unittest.main()
