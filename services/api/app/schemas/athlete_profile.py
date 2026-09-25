"""Enriched athlete profile projection schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.athlete import AthleteResponse
from app.schemas.athlete_performance import AthletePerformanceResponse


class AthleteStatisticsEvidenceResponse(BaseModel):
    """One provider statistics observation exposed as SMS24 evidence."""

    model_config = ConfigDict(extra="forbid")

    observation_id: uuid.UUID
    source_id: uuid.UUID
    sport_id: uuid.UUID
    provider_competitor_id: uuid.UUID
    athlete_external_id: str
    scope: str
    period_label: str | None
    metrics: dict[str, Any]
    metadata: dict[str, Any]
    fetched_at: datetime
    source_updated_at: datetime | None


class AthleteStatisticsIdentityResponse(BaseModel):
    """Explicit SMS24 identity state used to resolve provider evidence."""

    model_config = ConfigDict(extra="forbid")

    linked: bool
    identity_link_id: uuid.UUID | None
    status: str | None
    method: str | None
    canonical_competitor_id: uuid.UUID | None


class AthleteStatisticsResponse(BaseModel):
    """Provider evidence attached through an explicit active identity link."""

    model_config = ConfigDict(extra="forbid")

    identity: AthleteStatisticsIdentityResponse
    observations: list[AthleteStatisticsEvidenceResponse]


class AthleteProfileResponse(BaseModel):
    """Read-only enriched SMS athlete profile projection."""

    model_config = ConfigDict(extra="forbid")

    athlete: AthleteResponse
    performances: list[AthletePerformanceResponse]
    statistics: AthleteStatisticsResponse
