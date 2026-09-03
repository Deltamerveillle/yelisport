"""SMS Nations athlete country eligibility schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


EligibilityStatus = Literal[
    "declared",
    "documented",
    "verified",
]


class AthleteCountryEligibilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_id: uuid.UUID
    is_primary: bool = False


class AthleteCountryEligibilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    athlete_id: uuid.UUID
    country_id: uuid.UUID
    status: EligibilityStatus
    is_primary: bool
    declared_at: datetime
    documented_at: datetime | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime
