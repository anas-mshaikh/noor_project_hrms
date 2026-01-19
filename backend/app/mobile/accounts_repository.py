from __future__ import annotations

"""
Repository helpers for `mobile_accounts`.

We keep DB access in a small module so the service layer stays focused on orchestration
(Firebase Auth + Firestore + transactional updates).
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import MobileAccount


def get_mobile_account_by_employee(db: Session, store_id: UUID, employee_id: UUID) -> MobileAccount | None:
    return (
        db.query(MobileAccount)
        .filter(MobileAccount.store_id == store_id, MobileAccount.employee_id == employee_id)
        .one_or_none()
    )


def get_mobile_account_by_uid(db: Session, firebase_uid: str) -> MobileAccount | None:
    return db.query(MobileAccount).filter(MobileAccount.firebase_uid == firebase_uid).one_or_none()

