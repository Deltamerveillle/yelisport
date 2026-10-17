"""Durable athlete decisions, separate from SMS administrative transitions."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SMSConnectAthleteResponseEvent(Base):
    __tablename__ = "sms_connect_athlete_response_events"
    __table_args__ = (
        CheckConstraint(
            "from_response IN ('pending', 'interested', 'declined')",
            name="ck_sms_connect_response_event_from",
        ),
        CheckConstraint(
            "to_response IN ('interested', 'declined')",
            name="ck_sms_connect_response_event_to",
        ),
        CheckConstraint(
            "from_response <> to_response",
            name="ck_sms_connect_response_event_changed",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sms_connect_interests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_response: Mapped[str] = mapped_column(String(30), nullable=False)
    to_response: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
