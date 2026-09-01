"""Athlete profile schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AthleteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    """Schema for creating a new athlete."""

    sport_id: uuid.UUID
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    nationality: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    city: str | None = Field(None, max_length=100)
    biography: str | None = None


class AthleteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    """Schema for updating an athlete."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    nationality: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    city: str | None = Field(None, max_length=100)
    biography: str | None = None


class AthleteResponse(BaseModel):
    """Schema for returning athlete data."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    sport_id: uuid.UUID
    first_name: str
    last_name: str
    nationality: str | None
    country: str | None
    city: str | None
    biography: str | None
    created_at: datetime
    updated_at: datetime
