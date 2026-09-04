"""SMS Passport schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AthletePassportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discipline: str | None = Field(None, max_length=120)
    category: str | None = Field(None, max_length=120)
    position: str | None = Field(None, max_length=120)
    club_name: str | None = Field(None, max_length=180)
    league_name: str | None = Field(None, max_length=180)
    team_name: str | None = Field(None, max_length=180)

    height_cm: int | None = Field(None, gt=0, le=300)
    weight_kg: int | None = Field(None, gt=0, le=500)

    dominant_side: str | None = Field(None, max_length=30)

    available_for_opportunities: bool = False

    sporting_summary: str | None = None


class AthletePassportUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discipline: str | None = Field(None, max_length=120)
    category: str | None = Field(None, max_length=120)
    position: str | None = Field(None, max_length=120)
    club_name: str | None = Field(None, max_length=180)
    league_name: str | None = Field(None, max_length=180)
    team_name: str | None = Field(None, max_length=180)

    height_cm: int | None = Field(None, gt=0, le=300)
    weight_kg: int | None = Field(None, gt=0, le=500)

    dominant_side: str | None = Field(None, max_length=30)

    available_for_opportunities: bool = False

    sporting_summary: str | None = None


class AthletePassportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    athlete_id: uuid.UUID

    discipline: str | None
    category: str | None
    position: str | None

    club_name: str | None
    league_name: str | None
    team_name: str | None

    height_cm: int | None
    weight_kg: int | None

    dominant_side: str | None

    available_for_opportunities: bool

    sporting_summary: str | None

    created_at: datetime
    updated_at: datetime
