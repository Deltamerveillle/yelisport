"""Provider-neutral and multisport SMS24 / Live data models."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SportsDataSource(Base):
    __tablename__ = "sports_data_sources"
    __table_args__ = (
        CheckConstraint(
            "health_status IN ('healthy', 'degraded', 'unavailable')",
            name="ck_sports_data_sources_health_status",
        ),
        CheckConstraint(
            "priority >= 0",
            name="ck_sports_data_sources_priority_nonnegative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    provider_type: Mapped[str] = mapped_column(
        String(40), default="api", server_default="api"
    )
    priority: Mapped[int] = mapped_column(
        Integer, default=100, server_default="100", index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )
    health_status: Mapped[str] = mapped_column(
        String(20), default="healthy", server_default="healthy", index=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SportsCompetition(Base):
    __tablename__ = "sports_competitions"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "external_id",
            name="uq_sports_competitions_source_external",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="RESTRICT"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_data_sources.id", ondelete="RESTRICT"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(200), index=True)
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    season: Mapped[str | None] = mapped_column(String(40), index=True)
    logo_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SportsCompetitor(Base):
    """
    A provider-neutral participant identity.

    A competitor may represent a team, athlete, pair, national selection
    or another sport-specific participant.
    """

    __tablename__ = "sports_competitors"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "external_id",
            name="uq_sports_competitors_source_external",
        ),
        CheckConstraint(
            "competitor_type IN "
            "('team', 'athlete', 'pair', 'selection', 'other')",
            name="ck_sports_competitors_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="RESTRICT"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_data_sources.id", ondelete="RESTRICT"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(160))
    competitor_type: Mapped[str] = mapped_column(
        String(20), default="team", server_default="team", index=True
    )
    name: Mapped[str] = mapped_column(String(200), index=True)
    short_name: Mapped[str | None] = mapped_column(String(100))
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    logo_url: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SportsCanonicalFixture(Base):
    """Provider-independent identity for one real-world sports fixture."""

    __tablename__ = "sports_canonical_fixtures"
    __table_args__ = (
        UniqueConstraint(
            "canonical_key",
            name="uq_sports_canonical_fixtures_key",
        ),
        Index(
            "ix_sports_canonical_fixtures_lookup",
            "sport_id",
            "participant_signature",
            "starts_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="RESTRICT"), index=True
    )
    canonical_key: Mapped[str] = mapped_column(String(80))
    participant_signature: Mapped[str] = mapped_column(String(64))
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SportsFixture(Base):
    """
    A normalized sport contest/session/event supplied by an external source.

    Participants live in sports_fixture_participants so this works for
    two-sided contests as well as multi-participant events.
    """

    __tablename__ = "sports_fixtures"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "external_id",
            name="uq_sports_fixtures_source_external",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'live', 'finished', 'postponed', "
            "'cancelled', 'suspended', 'unknown')",
            name="ck_sports_fixtures_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="RESTRICT"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_data_sources.id", ondelete="RESTRICT"), index=True
    )
    competition_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sports_competitions.id", ondelete="SET NULL"), index=True
    )
    canonical_fixture_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "sports_canonical_fixtures.id",
            ondelete="SET NULL",
            name="fk_sports_fixtures_canonical_fixture_id",
        ),
        index=True,
    )
    external_id: Mapped[str] = mapped_column(String(160))
    name: Mapped[str | None] = mapped_column(String(240))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="scheduled", server_default="scheduled", index=True
    )
    live_clock: Mapped[str | None] = mapped_column(String(40))
    venue: Mapped[str | None] = mapped_column(String(240))
    result_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SportsFixtureParticipant(Base):
    __tablename__ = "sports_fixture_participants"
    __table_args__ = (
        UniqueConstraint(
            "fixture_id",
            "competitor_id",
            name="uq_sports_fixture_participant",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_sports_fixture_participants_position_nonnegative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fixture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_fixtures.id", ondelete="CASCADE"), index=True
    )
    competitor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_competitors.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    role: Mapped[str | None] = mapped_column(String(40))
    score_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    result_status: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
