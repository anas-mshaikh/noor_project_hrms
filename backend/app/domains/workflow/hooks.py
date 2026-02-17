from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.shared.types import AuthContext


class WorkflowEntityHandler(Protocol):
    """
    Optional domain hook invoked by the workflow engine when a request reaches a
    terminal state.

    Implementations must:
    - be tenant-safe (never bypass tenant filters)
    - be idempotent (may be called more than once due to retries)
    - NOT call db.commit(); they run inside the workflow transaction
    """

    def on_approved(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None: ...

    def on_rejected(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None: ...

    def on_cancelled(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None: ...


_HANDLERS: dict[str, WorkflowEntityHandler] = {}


def register(entity_type: str, handler: WorkflowEntityHandler) -> None:
    _HANDLERS[entity_type] = handler


def get(entity_type: str | None) -> WorkflowEntityHandler | None:
    if not entity_type:
        return None
    return _HANDLERS.get(entity_type)

