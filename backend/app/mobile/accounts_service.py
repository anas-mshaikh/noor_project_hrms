from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.mobile.firebase_admin import get_auth_module, get_firestore_client
from app.mobile.accounts_repository import (
    get_mobile_account_by_employee,
    get_mobile_account_by_uid,
)
from app.models.models import MobileAccount

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Small helper so tests can monkeypatch if needed."""
    return datetime.now(timezone.utc)


def _build_firestore_mapping_doc(
    row: MobileAccount, *, department: str | None
) -> dict[str, Any]:
    """
    Build the Firestore `users/{uid}` document payload.

    IMPORTANT:
    - This is the *only* document the mobile app needs to bootstrap org/store context.
    - Firestore remains a cache; Postgres is the source-of-truth.
    """
    return {
        "tenant_id": str(row.tenant_id),
        "branch_id": str(row.branch_id),
        "employee_id": str(row.employee_id),
        "employee_code": row.employee_code,
        # Keeping department here avoids an extra read on the mobile client
        # when it wants to show the "department leaderboard" immediately.
        "department": department,
        "role": row.role,
        "active": row.active,
        # Firestore can store Python datetime as a timestamp value via firebase-admin.
        "created_at": row.created_at,
        "revoked_at": row.revoked_at,
    }


class MobileAccountService:
    """
    Service layer for provisioning/revoking mobile access.

    Provisioning flow (email/password MVP):
      - Create Firebase Auth user -> get uid
      - Insert Postgres `mobile_accounts` row
      - Upsert Firestore `users/{uid}` mapping doc (merge=true)

    Revocation flow:
      - Mark Postgres row inactive + revoked_at
      - Disable Firebase Auth user
      - Update Firestore mapping doc active=false (merge=true)

    Dry-run:
      If `MOBILE_MAPPING_DRY_RUN=true`, we do NOT call Firebase.
      We only log the payload we *would* write.
    """

    def __init__(self, db: Session):
        self.db = db

    def _resolve_employee_code_and_department(
        self, *, tenant_id: UUID, branch_id: UUID, employee_id: UUID
    ) -> tuple[str, str | None]:
        row = self.db.execute(
            sa.text(
                """
                WITH current_employment AS (
                  SELECT
                    ee.employee_id,
                    ee.branch_id,
                    ee.org_unit_id,
                    ROW_NUMBER() OVER (
                      PARTITION BY ee.employee_id
                      ORDER BY ee.is_primary DESC NULLS LAST, ee.start_date DESC, ee.id DESC
                    ) AS rn
                  FROM hr_core.employee_employment ee
                  WHERE ee.tenant_id = :tenant_id
                    AND ee.end_date IS NULL
                ),
                ce AS (
                  SELECT * FROM current_employment WHERE rn = 1
                )
                SELECT
                  e.employee_code AS employee_code,
                  ou.name AS department
                FROM hr_core.employees e
                JOIN ce ON ce.employee_id = e.id
                LEFT JOIN tenancy.org_units ou ON ou.id = ce.org_unit_id
                WHERE e.id = :employee_id
                  AND e.tenant_id = :tenant_id
                  AND e.status = 'ACTIVE'
                  AND ce.branch_id = :branch_id
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id, "employee_id": employee_id},
        ).first()
        if row is None:
            raise ValueError("employee not found in branch")
        return str(row.employee_code), (str(row.department) if row.department else None)

    def provision_mobile_access(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        employee_id: UUID,
        email: str | None,
        phone_number: str | None = None,
        role: str = "employee",
        temp_password: str | None = None,
    ) -> tuple[MobileAccount, str | None]:
        """
        Provision mobile access for an employee.

        Returns:
        - MobileAccount row (DB source-of-truth)
        - generated_password (only when email flow and password was auto-generated)

        Idempotency rules:
        - If an account already exists for (branch_id, employee_id), we reuse it.
        - If the existing mapping is inactive, we reactivate it and re-sync Firebase.
        """
        # Validate branch exists in tenant (avoid leaking info via FK errors).
        branch_exists = self.db.execute(
            sa.text(
                "SELECT 1 FROM tenancy.branches WHERE id = :branch_id AND tenant_id = :tenant_id"
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id},
        ).first()
        if branch_exists is None:
            raise ValueError("branch not found")

        employee_code, department = self._resolve_employee_code_and_department(
            tenant_id=tenant_id, branch_id=branch_id, employee_id=employee_id
        )

        existing = (
            get_mobile_account_by_employee(
                self.db, tenant_id=tenant_id, branch_id=branch_id, employee_id=employee_id
            )
        )

        if existing is not None:
            # Ensure role/code stay in sync with current Employee record.
            existing.employee_code = employee_code
            existing.role = role
            if not existing.active:
                existing.active = True
                existing.revoked_at = None

            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)

            # Re-sync Firebase mapping (and re-enable Auth user) to keep derived cache consistent.
            self._firebase_enable_user(existing.firebase_uid)
            # Optional: reset the password if the admin explicitly provides one.
            #
            # We do NOT auto-rotate passwords for existing accounts because it can be surprising,
            # but for an MVP onboarding flow it's common to want a known temp password again.
            if temp_password:
                self._firebase_set_user_password(existing.firebase_uid, temp_password)
            self._firestore_upsert_user_mapping(existing, department=department)

            return existing, None

        # Create Firebase Auth user (preferred: email/password).
        uid, generated_password = self._firebase_create_user(
            email=email,
            phone_number=phone_number,
            temp_password=temp_password,
        )

        row = MobileAccount(
            tenant_id=tenant_id,
            branch_id=branch_id,
            employee_id=employee_id,
            employee_code=employee_code,
            firebase_uid=uid,
            role=role,
            active=True,
            revoked_at=None,
        )

        try:
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        except IntegrityError as e:
            # If a concurrent request created the row, fall back to reading it.
            self.db.rollback()
            logger.warning(
                "mobile provision race: branch_id=%s employee_id=%s err=%s",
                branch_id,
                employee_id,
                e,
            )
            row = (
                get_mobile_account_by_employee(
                    self.db, tenant_id=tenant_id, branch_id=branch_id, employee_id=employee_id
                )
            )
            if row is None:  # defensive: should not happen after IntegrityError
                raise RuntimeError("mobile account insert raced but lookup returned none")

        self._firestore_upsert_user_mapping(row, department=department)
        return row, generated_password

    def revoke_mobile_access(
        self, *, employee_id: UUID | None = None, firebase_uid: str | None = None
    ) -> MobileAccount:
        """
        Revoke mobile access.

        We support identifying the mapping either by:
        - employee_id (preferred from admin UI)
        - firebase_uid (useful for support tooling)
        """

        if employee_id is None and firebase_uid is None:
            raise ValueError("employee_id or firebase_uid required")

        q = self.db.query(MobileAccount)
        if firebase_uid is not None:
            row = get_mobile_account_by_uid(self.db, firebase_uid)
        else:
            # For revoke-by-employee_id we don't know branch_id; revoke across branches is ok.
            row = q.filter(MobileAccount.employee_id == employee_id).one_or_none()

        if row is None:
            raise ValueError("mobile account not found")

        row.active = False
        row.revoked_at = _utcnow()
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)

        self._firebase_disable_user(row.firebase_uid)
        _code, department = self._resolve_employee_code_and_department(
            tenant_id=row.tenant_id, branch_id=row.branch_id, employee_id=row.employee_id
        )
        self._firestore_upsert_user_mapping(row, department=department)

        return row

    def resync_mobile_mapping(self, *, firebase_uid: str) -> MobileAccount:
        """
        Upsert Firestore `users/{uid}` using the Postgres row as source-of-truth.
        """
        row = get_mobile_account_by_uid(self.db, firebase_uid)
        if row is None:
            raise ValueError("mobile account not found")

        _code, department = self._resolve_employee_code_and_department(
            tenant_id=row.tenant_id, branch_id=row.branch_id, employee_id=row.employee_id
        )
        self._firestore_upsert_user_mapping(row, department=department)
        return row

    # -----------------------------
    # Firebase helpers (isolated)
    # -----------------------------

    def _firebase_create_user(
        self,
        *,
        email: str | None,
        phone_number: str | None,
        temp_password: str | None,
    ) -> tuple[str, str | None]:
        """
        Create a Firebase Auth user and return (uid, generated_password?).

        We implement two provisioning modes:
        A) Email/password (MVP)
        B) Phone number (future-friendly) - we can create the user with phone_number
           so the client can use Firebase Phone Auth to sign in later.
        """

        if email is None and phone_number is None:
            raise ValueError("email or phone_number required")

        if settings.mobile_mapping_dry_run:
            # In dry-run mode we generate a fake uid so the rest of the flow can be tested.
            fake_uid = f"dryrun_{secrets.token_hex(12)}"
            logger.info(
                "mobile mapping dry-run: would create firebase auth user uid=%s email=%s phone=%s",
                fake_uid,
                email,
                phone_number,
            )
            return fake_uid, None

        auth = get_auth_module()

        if email is not None:
            generated_password = None
            password = temp_password
            if not password:
                # Token URL-safe, but we keep it short for easier onboarding.
                generated_password = secrets.token_urlsafe(12)
                password = generated_password

            user = auth.create_user(email=email, password=password)
            return user.uid, generated_password

        # Phone provisioning (no OTP handled here; the mobile app uses Firebase Phone Auth).
        user = auth.create_user(phone_number=phone_number)
        return user.uid, None

    def _firebase_disable_user(self, uid: str) -> None:
        if settings.mobile_mapping_dry_run:
            logger.info("mobile mapping dry-run: would disable auth user uid=%s", uid)
            return

        auth = get_auth_module()
        auth.update_user(uid, disabled=True)

    def _firebase_enable_user(self, uid: str) -> None:
        if settings.mobile_mapping_dry_run:
            logger.info("mobile mapping dry-run: would enable auth user uid=%s", uid)
            return

        auth = get_auth_module()
        auth.update_user(uid, disabled=False)

    def _firebase_set_user_password(self, uid: str, password: str) -> None:
        """
        Set (or reset) a Firebase Auth user's password.

        This is used only when an admin explicitly provides `temp_password` in the
        provisioning request. It keeps the flow "no manual Firebase console steps".
        """
        if settings.mobile_mapping_dry_run:
            logger.info(
                "mobile mapping dry-run: would set auth password uid=%s",
                uid,
            )
            return

        auth = get_auth_module()
        auth.update_user(uid, password=password)

    def _firestore_upsert_user_mapping(self, row: MobileAccount, *, department: str | None) -> None:
        payload = _build_firestore_mapping_doc(row, department=department)

        logger.info(
            "firestore users/{uid} upsert: uid=%s employee_id=%s branch_id=%s active=%s",
            row.firebase_uid,
            row.employee_id,
            row.branch_id,
            row.active,
        )

        if settings.mobile_mapping_dry_run:
            logger.info("mobile mapping dry-run payload: %s", payload)
            return

        client = get_firestore_client()
        doc = client.collection("users").document(row.firebase_uid)
        # merge=True allows adding new fields later without overwriting unknown ones.
        doc.set(payload, merge=True)
