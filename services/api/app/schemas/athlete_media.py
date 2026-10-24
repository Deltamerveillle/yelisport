"""Validated media metadata registered after an authenticated storage upload."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MediaType = Literal["photo", "video"]
MediaMime = Literal["image/jpeg", "image/png", "image/webp", "video/mp4"]


class AthleteMediaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage_path: str = Field(min_length=10, max_length=320)
    media_type: MediaType
    mime_type: MediaMime
    duration_seconds: int | None = Field(default=None, ge=15, le=30)


class AthleteMediaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    athlete_id: uuid.UUID
    storage_path: str
    media_type: MediaType
    mime_type: str
    duration_seconds: int | None
    moderation_status: str
    created_at: datetime
