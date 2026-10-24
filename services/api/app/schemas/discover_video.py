"""Schemas for SMS Discover videos."""

import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

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

    video_url: HttpUrl | None = None
    thumbnail_url: HttpUrl | None = None
    caption: str | None = Field(default=None, max_length=1000)
    duration_seconds: int | None = Field(default=None, ge=15, le=30)
    visibility: VisibilityStatus | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> Self:
        """Explicit null cannot clear database-required fields in a partial update."""
        for field in ("video_url", "duration_seconds", "visibility"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


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
