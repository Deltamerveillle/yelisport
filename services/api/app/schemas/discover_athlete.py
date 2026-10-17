"""Public projection schemas for SMS Discover athletes."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.athlete_passport import AthletePassportResponse
from app.schemas.athlete_performance import AthletePerformanceResponse
from app.schemas.discover_video import DiscoverVideoResponse


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


class DiscoverAthletePublicStatisticsEvidenceResponse(BaseModel):
    """Public-safe SMS24 statistics evidence for a discoverable athlete."""

    model_config = ConfigDict(extra="forbid")

    scope: str
    period_label: str | None
    metrics: dict[str, object]
    fetched_at: datetime
    source_updated_at: datetime | None


class DiscoverAthletePublicStatisticsResponse(BaseModel):
    """Public statistics exposed only through an explicit SMS24 identity link."""

    model_config = ConfigDict(extra="forbid")

    linked: bool
    observations: list[DiscoverAthletePublicStatisticsEvidenceResponse]


class DiscoverAthleteProfileResponse(BaseModel):
    """Public commercial showcase for an SMS Discover athlete."""

    model_config = ConfigDict(extra="forbid")

    athlete: DiscoverAthleteIdentityResponse
    passport: AthletePassportResponse
    performances: list[AthletePerformanceResponse]
    statistics: DiscoverAthletePublicStatisticsResponse
    videos: list[DiscoverVideoResponse]

