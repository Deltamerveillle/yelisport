"""Public schemas for SMS subscriptions."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubscriptionResponse(BaseModel):
    """Safe subscription representation exposed to its owner."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_code: str
    status: str
    provider: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    created_at: datetime
    updated_at: datetime


class SubscriptionAccessResponse(BaseModel):
    """Current SMS access rights for the authenticated user."""

    has_premium_access: bool
    plan_code: str
    status: str
    current_period_end: datetime | None
