"""
Workflow hook adapter for profile change requests (Milestone 6).

This module connects Workflow Engine v1 terminal transitions to the profile
change domain side-effects.

Why an adapter class?
- Keeps the workflow hook interface small and stable.
- Allows the domain service to be unit-testable without the workflow engine.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domains.profile_change.service import ProfileChangeApplyService
from app.shared.types import AuthContext


class ProfileChangeWorkflowHandler:
    """
    Workflow entity handler for entity_type="hr_core.profile_change_request".
    """

    def __init__(self) -> None:
        self._svc = ProfileChangeApplyService()

    def on_approved(
        self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]
    ) -> None:
        self._svc.on_workflow_approved(db, ctx=ctx, workflow_request=workflow_request)

    def on_rejected(
        self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]
    ) -> None:
        self._svc.on_workflow_rejected(db, ctx=ctx, workflow_request=workflow_request)

    def on_cancelled(
        self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]
    ) -> None:
        self._svc.on_workflow_cancelled(db, ctx=ctx, workflow_request=workflow_request)
