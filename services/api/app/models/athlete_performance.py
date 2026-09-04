"""Multisport athlete performance model for SMS."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
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


class AthletePerformance(Base):
    """Structured multisport performance attached to an athlete."""

    __tablename__ = "athlete_performances"

    __table_args__ = (
        CheckConstraint(
            "verification_status IN "
            "('declared', 'documented', 'verified')",
            name="ck_athlete_performances_verification_status",
        ),
        Index(
            "ix_athlete_performances_athlete_date",
            "athlete_id",
            "performance_date",
        ),
        Index(
            "ix_athlete_performances_sport_date",
            "sport_id",
            "performance_date",
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

    sport_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sports.id"),
        nullable=False,
        index=True,
    )

    discipline: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    performance_type: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )

    competition_name: Mapped[str | None] = mapped_column(
        String(180),
        nullable=True,
        index=True,
    )

    season: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    performance_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    # Sport-specific values.
    #
    # Examples:
    # Football:
    # {
    #   "goals": 2,
    #   "assists": 1,
    #   "minutes": 90
    # }
    #
    # Athletics:
    # {
    #   "time_seconds": 10.42,
    #   "distance_meters": 100
    # }
    #
    # Basketball:
    # {
    #   "points": 24,
    #   "rebounds": 8,
    #   "assists": 5
    # }
    metrics: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    verification_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="declared",
        server_default="declared",
        index=True,
    )

    source_name: Mapped[str | None] = mapped_column(
        String(180),
        nullable=True,
    )

    source_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
