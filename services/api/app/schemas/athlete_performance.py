"""Schemas for SMS multisport athlete performances."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)


VerificationStatus = Literal[
    "declared",
    "documented",
    "verified",
]


class AthletePerformanceCreate(BaseModel):
    """Payload an athlete may submit for a performance."""

    model_config = ConfigDict(extra="forbid")

    discipline: str | None = Field(
        default=None,
        max_length=120,
    )
    performance_type: str | None = Field(
        default=None,
        max_length=80,
    )
    competition_name: str | None = Field(
        default=None,
        max_length=180,
    )
    season: str | None = Field(
        default=None,
        max_length=50,
    )
    performance_date: date

    metrics: dict[str, Any] = Field(
        default_factory=dict,
    )

    summary: str | None = Field(
        default=None,
        max_length=5000,
    )

    source_name: str | None = Field(
        default=None,
        max_length=180,
    )
    source_url: HttpUrl | None = None


class AthletePerformanceUpdate(BaseModel):
    """Fields an athlete may change on a declared performance."""

    model_config = ConfigDict(extra="forbid")

    discipline: str | None = Field(
        default=None,
        max_length=120,
    )
    performance_type: str | None = Field(
        default=None,
        max_length=80,
    )
    competition_name: str | None = Field(
        default=None,
        max_length=180,
    )
    season: str | None = Field(
        default=None,
        max_length=50,
    )
    performance_date: date | None = None
    metrics: dict[str, Any] | None = None

    summary: str | None = Field(
        default=None,
        max_length=5000,
    )

    source_name: str | None = Field(
        default=None,
        max_length=180,
    )
    source_url: HttpUrl | None = None

    @field_validator(
        "performance_date",
        "metrics",
    )
    @classmethod
    def non_nullable_fields_cannot_be_null(
        cls,
        value,
    ):
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class AthletePerformanceResponse(BaseModel):
    """API representation of one SMS performance."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    athlete_id: uuid.UUID
    sport_id: uuid.UUID

    discipline: str | None
    performance_type: str | None
    competition_name: str | None
    season: str | None

    performance_date: date
    metrics: dict[str, Any]

    summary: str | None

    verification_status: VerificationStatus

    source_name: str | None
    source_url: str | None

    created_at: datetime
    updated_at: datetime
