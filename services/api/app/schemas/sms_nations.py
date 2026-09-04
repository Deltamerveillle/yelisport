"""Schemas for SMS Nations athlete discovery."""

import uuid

from pydantic import BaseModel, ConfigDict


class SMSNationAthleteResponse(BaseModel):
    """Public/professional athlete card for SMS Nations."""

    model_config = ConfigDict(from_attributes=True)

    athlete_id: uuid.UUID
    first_name: str
    last_name: str
    city: str | None
    avatar_url: str | None

    sport_id: uuid.UUID
    sport_slug: str
    sport_name: str

    residence_country_id: uuid.UUID | None
    residence_country_iso2: str | None
    residence_country_name: str | None

    discipline: str | None
    category: str | None
    position: str | None
    club_name: str | None
    league_name: str | None
    team_name: str | None
    available_for_opportunities: bool | None

    eligibility_country_id: uuid.UUID | None
    eligibility_status: str | None
    eligibility_is_primary: bool | None

    discover_video_id: uuid.UUID | None
    discover_video_url: str | None
    discover_thumbnail_url: str | None
    discover_caption: str | None
    discover_duration_seconds: int | None


class SMSNationsSearchResponse(BaseModel):
    """Paginated SMS Nations discovery response."""

    items: list[SMSNationAthleteResponse]
    total: int
    limit: int
    offset: int
