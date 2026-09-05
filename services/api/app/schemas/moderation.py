"""Schemas for SMS moderation."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ModerationResourceType = Literal[
    "user",
    "athlete",
    "discover_video",
    "sms_connect_interest",
]

ModerationReason = Literal[
    "spam",
    "fraud",
    "abuse",
    "inappropriate_content",
    "impersonation",
    "safety",
    "other",
]

ModerationStatus = Literal[
    "submitted",
    "under_review",
    "resolved",
    "dismissed",
]


class ModerationReportCreate(BaseModel):
    """Create one user moderation report."""

    model_config = ConfigDict(extra="forbid")

    resource_type: ModerationResourceType
    resource_id: uuid.UUID
    reason: ModerationReason
    details: str | None = Field(
        default=None,
        max_length=5000,
    )


class ModerationReportResponse(BaseModel):
    origin: Literal["user_report", "publication_review"] = "user_report"
    """Safe report response for the reporting user."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resource_type: ModerationResourceType
    resource_id: uuid.UUID
    reason: ModerationReason
    details: str | None
    status: ModerationStatus
    created_at: datetime
    updated_at: datetime


class ModerationAdminReportResponse(
    ModerationReportResponse
):
    """Administrative report view."""

    reporter_user_id: uuid.UUID


class ModerationTransitionRequest(BaseModel):
    """Administrative moderation state transition."""

    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "under_review",
        "resolved",
        "dismissed",
    ]

    note: str | None = Field(
        default=None,
        max_length=5000,
    )


class ModerationEventResponse(BaseModel):
    """Safe administrative moderation audit event."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    actor_role: str
    action: str
    from_status: str | None
    to_status: str | None
    note: str | None
    created_at: datetime



class DiscoverModerationDecision(BaseModel):
    """Admin decision for one Discover moderation case."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    note: str | None = Field(
        default=None,
        max_length=5000,
    )



class UserModerationAction(BaseModel):
    """Admin suspension or reactivation decision."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["suspend", "reactivate"]
    note: str | None = Field(
        default=None,
        max_length=5000,
    )


class UserModerationResponse(BaseModel):
    """Safe admin response after a user moderation action."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
