"""Public SMS24 Live response schemas."""

from datetime import datetime
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SMS24ParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    competitor_id: uuid.UUID
    competitor_type: str
    name: str
    short_name: str | None
    country_code: str | None
    logo_url: str | None
    position: int
    role: str | None
    score: dict[str, Any] = Field(default_factory=dict)
    result_status: str | None


class SMS24FixtureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID

    sport_slug: str
    sport_name: str

    source_slug: str
    source_name: str

    competition_id: uuid.UUID | None
    competition_name: str | None
    competition_country_code: str | None
    season: str | None

    name: str | None
    starts_at: datetime
    status: str
    live_clock: str | None
    venue: str | None

    result: dict[str, Any] = Field(default_factory=dict)

    source_updated_at: datetime | None
    fetched_at: datetime

    participants: list[SMS24ParticipantResponse]


class SMS24SourceHealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    provider_type: str
    health_status: str
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_checked_at: datetime | None
