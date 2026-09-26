"""Public commercial offers and owner-safe payment representations."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

PlanCode = Annotated[str, Field(strict=True, pattern=r"^[a-z][a-z0-9_-]{0,49}$")]


class CommercialPlan(BaseModel):
    """Server configuration; duration is a fixed prepaid term, not auto-renewal."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    plan_code: PlanCode
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(max_length=1000)
    amount_minor: int = Field(gt=0, le=2147483647)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    duration_days: int = Field(gt=0, le=3660)
    active: bool = False
    purchasable: bool = False

    @field_validator("plan_code")
    @classmethod
    def paid_plan(cls, value: str) -> str:
        if value == "free":
            raise ValueError("Free access cannot be sold")
        return value

    @field_validator("name", "description")
    @classmethod
    def public_text(cls, value: str) -> str:
        if "\x00" in value or (value and not value.strip()):
            raise ValueError("Invalid public text")
        return value


class PaymentInitiationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: PlanCode


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    plan_code: str
    amount_minor: int
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime
