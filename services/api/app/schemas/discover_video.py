"""Schemas for SMS Discover videos."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


PublicationStatus = Literal["draft", "published", "archived"]
ModerationStatus = Literal["pending", "approved", "rejected", "flagged"]
VisibilityStatus = Literal["public", "private", "unlisted"]


class DiscoverVideoCreate(BaseModel):
    """Payload accepted when an athlete creates a Discover video."""

    model_config = ConfigDict(extra="forbid")

    video_url: HttpUrl
    thumbnail_url: HttpUrl | None = None
    caption: str | None = Field(default=None, max_length=1000)
    duration_seconds: int = Field(ge=15, le=30)
    visibility: VisibilityStatus = "public"


class DiscoverVideoUpdate(BaseModel):
    """Fields the athlete is allowed to update."""

    model_config = ConfigDict(extra="forbid")

    video_url: HttpUrl = None
    thumbnail_url: HttpUrl | None = None
    caption: str | None = Field(default=None, max_length=1000)
    duration_seconds: int = Field(default=None, ge=15, le=30)
    visibility: VisibilityStatus = None


class DiscoverVideoResponse(BaseModel):
    """API representation of an SMS Discover video."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    athlete_id: uuid.UUID
    video_url: str
    thumbnail_url: str | None
    caption: str | None
    duration_seconds: int
    publication_status: PublicationStatus
    moderation_status: ModerationStatus
    visibility: VisibilityStatus
    is_active: bool
    view_count: int
    created_at: datetime
    updated_at: datetime
