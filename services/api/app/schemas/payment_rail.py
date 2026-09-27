"""Internal rail contracts. Normalized PSP evidence is not a trusted SMS event."""

import uuid
from typing import Annotated, Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

RailCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,49}$")]
ExternalReference = Annotated[str, Field(min_length=1, max_length=255)]


class RailMessage(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    @field_validator("*", check_fields=False)
    @classmethod
    def safe_text(cls, value):
        if isinstance(value, str) and (not value.strip() or "\x00" in value):
            raise ValueError("Invalid rail text")
        return value


class RailInitializationRequest(RailMessage):
    # Generated locally; reused for every remote retry of this same intention.
    idempotency_key: uuid.UUID
    payment_reference: str = Field(min_length=1, max_length=100)
    amount_minor: int = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class RailInitializationResult(RailMessage):
    external_transaction_id: ExternalReference


class RailVerificationRequest(RailMessage):
    external_transaction_id: ExternalReference
    payment_reference: str = Field(min_length=1, max_length=100)


class RailVerificationResult(RailVerificationRequest):
    status: Literal["pending", "succeeded", "failed"]
    # Evidence to compare with SMS snapshots, never authoritative commercial terms.
    observed_amount_minor: int = Field(gt=0)
    observed_currency: str = Field(pattern=r"^[A-Z]{3}$")
    payment_effective_at: AwareDatetime | None = None


class PaymentRail(Protocol):
    """Implemented later using official PSP documentation and authenticated verification.

    Implementations receive immutable values, not ORM entities or a database session.
    Results cannot set plans, duration or entitlements and must never be routed directly
    to YeleniPayEventService without the future trusted gateway verification boundary.
    """

    async def initialize_payment(
        self,
        request: RailInitializationRequest,
    ) -> RailInitializationResult: ...

    async def verify_payment(
        self,
        request: RailVerificationRequest,
    ) -> RailVerificationResult: ...
