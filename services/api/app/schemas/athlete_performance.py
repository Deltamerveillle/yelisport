"""Schemas for SMS athlete performances."""

import math
import re
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


_METRIC_KEY_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]{0,63}$"
)

_MAX_METRICS = 100
_MAX_METRIC_STRING_LENGTH = 500


def _validate_metrics(
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate sport-specific performance metrics.

    SMS accepts flat scalar metrics only:
    numbers, strings and booleans.

    Nested JSON, lists, null values and unsafe metric names
    are intentionally rejected so SMS Nations can filter
    metrics safely.
    """

    if len(metrics) > _MAX_METRICS:
        raise ValueError(
            f"metrics cannot contain more than "
            f"{_MAX_METRICS} entries"
        )

    for key, value in metrics.items():
        if not _METRIC_KEY_PATTERN.fullmatch(key):
            raise ValueError(
                "Metric keys must match "
                "^[a-z][a-z0-9_]{0,63}$"
            )

        if value is None:
            raise ValueError(
                f"Metric '{key}' cannot be null"
            )

        if isinstance(value, bool):
            continue

        if isinstance(value, int):
            continue

        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError(
                    f"Metric '{key}' must be finite"
                )
            continue

        if isinstance(value, str):
            if len(value) > _MAX_METRIC_STRING_LENGTH:
                raise ValueError(
                    f"Metric '{key}' string value is too long"
                )
            continue

        raise ValueError(
            f"Metric '{key}' must be a scalar "
            "number, string or boolean"
        )

    return metrics


class AthletePerformanceCreate(BaseModel):
    """Athlete-submitted SMS performance."""

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

    @field_validator("metrics")
    @classmethod
    def validate_metrics(
        cls,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        return _validate_metrics(value)


class AthletePerformanceUpdate(BaseModel):
    """Fields an athlete may change on a performance."""

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

    @field_validator("performance_date")
    @classmethod
    def performance_date_cannot_be_null(
        cls,
        value: date | None,
    ) -> date:
        if value is None:
            raise ValueError("Field cannot be null")
        return value

    @field_validator("metrics")
    @classmethod
    def validate_metrics(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if value is None:
            raise ValueError("Field cannot be null")

        return _validate_metrics(value)


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
