from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domains.leave.service import LeaveService
from app.shared.types import AuthContext


class LeaveWorkflowHandler:
    """
    Workflow entity handler for entity_type = "leave.leave_request".
    """

    def __init__(self) -> None:
        self._svc = LeaveService()

    def on_approved(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        self._svc.on_workflow_approved(db, ctx=ctx, workflow_request=workflow_request)

    def on_rejected(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        self._svc.on_workflow_rejected(db, ctx=ctx, workflow_request=workflow_request)

    def on_cancelled(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        self._svc.on_workflow_cancelled(db, ctx=ctx, workflow_request=workflow_request)

