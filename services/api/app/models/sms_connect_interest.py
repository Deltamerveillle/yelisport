"""Professional interest requests for SMS Connect."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SMSConnectInterest(Base):
    __tablename__ = "sms_connect_interests"

    __table_args__ = (
        CheckConstraint(
            "interest_type IN "
            "('trial', 'recruitment', 'contract', "
            "'partnership', 'information')",
            name="ck_sms_connect_interest_type",
        ),
        CheckConstraint(
            "status IN "
            "('submitted', 'under_review', 'approved', "
            "'rejected', 'delivered', 'closed')",
            name="ck_sms_connect_interest_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    athlete_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "athletes.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    requester_role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    interest_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    organization_name: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="submitted",
        server_default="submitted",
        index=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
