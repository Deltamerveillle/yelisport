"""Schemas for SMS Connect."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


InterestType = Literal[
    "trial",
    "recruitment",
    "contract",
    "partnership",
    "information",
]

InterestStatus = Literal[
    "submitted",
    "under_review",
    "approved",
    "rejected",
    "delivered",
    "closed",
]


class SMSConnectInterestCreate(BaseModel):
    """Professional interest submitted through SMS."""

    model_config = ConfigDict(
        extra="forbid"
    )

    interest_type: InterestType

    organization_name: str = Field(
        min_length=2,
        max_length=180,
    )

    subject: str = Field(
        min_length=2,
        max_length=180,
    )

    message: str = Field(
        min_length=10,
        max_length=5000,
    )


class SMSConnectInterestResponse(BaseModel):
    """Safe SMS Connect response."""

    model_config = ConfigDict(
        from_attributes=True
    )

    id: uuid.UUID
    athlete_id: uuid.UUID

    requester_role: str

    interest_type: InterestType
    organization_name: str
    subject: str
    message: str

    status: InterestStatus

    reviewed_at: datetime | None
    delivered_at: datetime | None

    created_at: datetime
    updated_at: datetime
