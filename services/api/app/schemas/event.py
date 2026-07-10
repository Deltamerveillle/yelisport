"""Sport event API contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventCreate(BaseModel):
    sport_id: uuid.UUID
    title: str = Field(min_length=3, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    location: str = Field(min_length=2, max_length=240)
    starts_at: datetime
    ends_at: datetime
    capacity: int = Field(gt=0, le=100_000)

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "EventCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at doit être postérieur à starts_at")
        return self


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sport_id: uuid.UUID
    organizer_id: uuid.UUID
    title: str
    description: str | None
    location: str
    starts_at: datetime
    ends_at: datetime
    capacity: int


class RegistrationResponse(BaseModel):
    event_id: uuid.UUID
    status: str
