"""SMS moderation reports and immutable administrative audit events."""

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
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModerationReport(Base):
    """User-submitted report reviewed by verified SMS administrators."""

    __tablename__ = "moderation_reports"

    __table_args__ = (
        CheckConstraint(
            "resource_type IN "
            "('user', 'athlete', 'discover_video', 'sms_connect_interest')",
            name="ck_moderation_reports_resource_type",
        ),
        CheckConstraint(
            "reason IN "
            "('spam', 'fraud', 'abuse', 'inappropriate_content', "
            "'impersonation', 'safety', 'other')",
            name="ck_moderation_reports_reason",
        ),
        CheckConstraint(
            "status IN "
            "('submitted', 'under_review', 'resolved', 'dismissed')",
            name="ck_moderation_reports_status",
        ),
        CheckConstraint(
            "origin IN "
            "('user_report', 'publication_review')",
            name="ck_moderation_reports_origin",
        ),
        Index(
            "uq_moderation_open_publication_review",
            "resource_type",
            "resource_id",
            "origin",
            unique=True,
            postgresql_where=text(
                "origin = 'publication_review' "
                "AND resource_type = 'discover_video' "
                "AND status IN ('submitted', 'under_review')"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    reporter_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    reason: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    origin: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="user_report",
        server_default="user_report",
        index=True,
    )

    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="submitted",
        server_default="submitted",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ModerationReportEvent(Base):
    """Immutable administrative audit record for one moderation report."""

    __tablename__ = "moderation_report_events"

    __table_args__ = (
        CheckConstraint(
            "action IN "
            "('submitted', 'under_review', 'resolved', 'dismissed', "
            "'discover_approved', 'discover_rejected', "
            "'user_suspended', 'user_reactivated')",
            name="ck_moderation_report_events_action",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "moderation_reports.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    actor_role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    from_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    to_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
