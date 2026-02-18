from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domains.attendance.service import AttendanceCorrectionService
from app.shared.types import AuthContext


class AttendanceCorrectionWorkflowHandler:
    """
    Workflow entity handler for entity_type = "attendance.attendance_correction".
    """

    def __init__(self) -> None:
        self._svc = AttendanceCorrectionService()

    def on_approved(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        self._svc.on_workflow_approved(db, ctx=ctx, workflow_request=workflow_request)

    def on_rejected(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        self._svc.on_workflow_rejected(db, ctx=ctx, workflow_request=workflow_request)

    def on_cancelled(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        self._svc.on_workflow_cancelled(db, ctx=ctx, workflow_request=workflow_request)

