"""Schemas for trusted YELENI Pay events."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class YeleniPayPaymentConfirmed(BaseModel):
    """Verified payment confirmation received from YELENI Pay."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=255)
    event_type: Literal["payment.confirmed"]

    reference: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=50)
    provider_transaction_id: str = Field(min_length=1, max_length=255)

    amount_minor: int = Field(gt=0)
    currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    )

    period_start: datetime
    period_end: datetime

    provider_customer_id: str | None = Field(
        default=None,
        max_length=255,
    )
    provider_subscription_id: str | None = Field(
        default=None,
        max_length=255,
    )


class YeleniPayPaymentFailed(BaseModel):
    """Verified payment failure received from YELENI Pay."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=255)
    event_type: Literal["payment.failed"]

    reference: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=50)
    provider_transaction_id: str | None = Field(
        default=None,
        max_length=255,
    )
