"""SMS-managed commercial relationship and its independent lifecycle audit."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SMSConnectOpportunity(Base):
    __tablename__ = "sms_connect_opportunities"
    __table_args__ = (
        UniqueConstraint("interest_id", name="uq_sms_connect_opportunities_interest"),
        CheckConstraint(
            "status IN ('active', 'progressing', 'successful', 'unsuccessful', 'withdrawn')",
            name="ck_sms_connect_opportunity_status",
        ),
        CheckConstraint(
            "(status IN ('active', 'progressing') AND closed_at IS NULL) OR "
            "(status IN ('successful', 'unsuccessful', 'withdrawn') AND closed_at IS NOT NULL)",
            name="ck_sms_connect_opportunity_closed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sms_connect_interests.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(30), default="active", server_default="active")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class SMSConnectOpportunityEvent(Base):
    __tablename__ = "sms_connect_opportunity_events"
    __table_args__ = (
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('active', 'progressing', 'successful', 'unsuccessful', 'withdrawn')",
            name="ck_sms_connect_opportunity_event_from",
        ),
        CheckConstraint(
            "to_status IN ('active', 'progressing', 'successful', 'unsuccessful', 'withdrawn')",
            name="ck_sms_connect_opportunity_event_to",
        ),
        CheckConstraint(
            "source IN ('athlete_consent', 'athlete_withdrawal', "
            "'athlete_reactivation', 'sms_admin')",
            name="ck_sms_connect_opportunity_event_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sms_connect_opportunities.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
