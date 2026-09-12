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


class SMS24StandingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sport_slug: str
    sport_name: str
    competition_id: uuid.UUID
    competition_name: str
    competition_country_code: str | None
    competition_jurisdiction_name: str | None
    season_id: uuid.UUID
    season_label: str
    canonical_competitor_id: uuid.UUID
    competitor_name: str
    competitor_type: str
    competitor_country_code: str | None
    competitor_identity_scope: str
    position: int
    points: int | None
    played: int | None
    wins: int | None
    draws: int | None
    losses: int | None
    goals_for: int | None
    goals_against: int | None
    goal_difference: int | None
    home_played: int | None
    home_wins: int | None
    home_draws: int | None
    home_losses: int | None
    home_goals_for: int | None
    home_goals_against: int | None
    home_points: int | None
    away_played: int | None
    away_wins: int | None
    away_draws: int | None
    away_losses: int | None
    away_goals_for: int | None
    away_goals_against: int | None
    away_points: int | None
    form: str | None
    description: str | None
    movement_status: str | None
    stage_external_id: str | None
    group_external_id: str | None
    group_name: str | None
    round_external_id: str | None
    standing_rule_external_id: str | None
    source_slug: str
    source_name: str
    provider_updated_at: datetime | None
    fetched_at: datetime


class SMS24SeasonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    starts_at: datetime | None
    ends_at: datetime | None
    is_current: bool


class SMS24CompetitionRelationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sport_slug: str
    sport_name: str
    country_code: str | None
    jurisdiction_name: str | None
    identity_scope: str
    seasons: list[SMS24SeasonResponse]


class SMS24CompetitionResponse(SMS24CompetitionRelationResponse):
    selected_season_id: uuid.UUID | None


class SMS24TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    competitor_type: str
    country_code: str | None
    identity_scope: str
    sport_slug: str
    sport_name: str
    competitions: list[SMS24CompetitionRelationResponse]


class SMS24PageParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    canonical_competitor_id: uuid.UUID | None
    competitor_type: str
    name: str
    short_name: str | None
    country_code: str | None
    logo_url: str | None
    position: int
    role: str | None
    score: dict[str, Any]
    result_status: str | None


class SMS24PageFixtureResponse(BaseModel):
    """Canonical navigation references; id remains the selected fixture observation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canonical_fixture_id: uuid.UUID | None
    canonical_competition_id: uuid.UUID | None
    canonical_season_id: None = None
    sport_slug: str
    sport_name: str
    source_slug: str
    source_name: str
    name: str | None
    starts_at: datetime
    status: str
    live_clock: str | None
    venue: str | None
    result: dict[str, Any]
    source_updated_at: datetime | None
    fetched_at: datetime
    participants: list[SMS24PageParticipantResponse]
