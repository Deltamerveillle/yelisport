"""Request and response schemas for SMS Proof."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SMSProofDecisionRequest(BaseModel):
    decision: Literal["declared", "documented", "verified"]
    reason: str = Field(min_length=1, max_length=5000)
    evidence: dict = Field(default_factory=dict)


class SMSProofVerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    performance_id: uuid.UUID
    verifier_user_id: uuid.UUID
    decision: Literal["declared", "documented", "verified"]
    reason: str
    evidence: dict
    created_at: datetime
