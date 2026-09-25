"""Public projection schemas for SMS Discover athletes."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.athlete_passport import AthletePassportResponse


class DiscoverAthleteIdentityResponse(BaseModel):
    """Public sporting identity exposed by SMS Discover."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    sport_id: uuid.UUID
    first_name: str
    last_name: str
    nationality: str | None
    country: str | None
    residence_country_id: uuid.UUID | None
    city: str | None
    biography: str | None
    created_at: datetime
    updated_at: datetime


class DiscoverAthleteResponse(BaseModel):
    """An athlete who explicitly opted in to opportunity discovery."""

    model_config = ConfigDict(extra="forbid")

    athlete: DiscoverAthleteIdentityResponse
    passport: AthletePassportResponse
