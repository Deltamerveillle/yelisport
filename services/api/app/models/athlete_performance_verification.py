"""Audit history of SMS Proof performance verification decisions."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AthletePerformanceVerification(Base):
    __tablename__ = "athlete_performance_verifications"

    __table_args__ = (
        CheckConstraint(
            "decision IN ('declared', 'documented', 'verified')",
            name="ck_sms_proof_verification_decision",
        ),
        CheckConstraint(
            "length(btrim(reason)) > 0",
            name="ck_sms_proof_verification_reason",
        ),
        Index(
            "ix_sms_proof_verifications_performance",
            "performance_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    performance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("athlete_performances.id", ondelete="RESTRICT"),
        nullable=False,
    )

    verifier_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    decision: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    evidence: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
