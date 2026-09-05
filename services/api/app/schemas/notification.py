"""Schemas for SMS notifications."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: uuid.UUID
    notification_type: str
    title: str
    body: str
    source: str
    resource_type: str | None
    resource_id: uuid.UUID | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int
