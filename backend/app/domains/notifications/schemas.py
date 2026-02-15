from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: UUID
    type: str
    title: str
    body: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    action_url: str | None = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime
    read_at: datetime | None = None


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    next_cursor: str | None = None


class UnreadCountOut(BaseModel):
    unread_count: int

