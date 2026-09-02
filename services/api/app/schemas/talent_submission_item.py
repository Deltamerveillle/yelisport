"""Schemas for private SMS Talent submission items."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


TalentSubmissionItemType = Literal[
    "video",
    "document",
    "performance",
    "proof",
]


class TalentSubmissionItemCreate(BaseModel):
    """Material added by the athlete to a Talent application."""

    model_config = ConfigDict(extra="forbid")

    item_type: TalentSubmissionItemType
    resource_url: HttpUrl
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    metadata_json: dict | None = None


class TalentSubmissionItemResponse(BaseModel):
    """Private Talent submission item representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    item_type: TalentSubmissionItemType
    resource_url: str
    title: str | None
    description: str | None
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime
