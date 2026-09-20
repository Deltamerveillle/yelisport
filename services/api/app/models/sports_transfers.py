"""Explicit human identity links, career movements, and provider provenance.

No relationship creates SMS users/profiles. Cross-table type/sport checks belong
in SMS24TransfersRepository; foreign keys and identity uniqueness live in PostgreSQL.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TransferTimestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SportsAthleteIdentityLink(TransferTimestamps, Base):
    """Explicit one-to-one active link; ended rows retain the decision history."""

    __tablename__ = "sports_athlete_identity_links"
    __table_args__ = (
        Index(
            "uq_sports_athlete_links_active_athlete",
            "athlete_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index(
            "uq_sports_athlete_links_active_competitor",
            "canonical_competitor_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        CheckConstraint(
            "status IN ('declared', 'documented', 'verified')",
            name="ck_sports_athlete_links_status",
        ),
        CheckConstraint(
            "method IN ('athlete_claim', 'manual_review', 'institutional_review')",
            name="ck_sports_athlete_links_method",
        ),
        CheckConstraint(
            "length(btrim(established_by)) > 0 AND length(btrim(evidence_reference)) > 0",
            name="ck_sports_athlete_links_provenance",
        ),
        CheckConstraint(
            "status != 'verified' OR (method = 'institutional_review' "
            "AND verified_at IS NOT NULL)",
            name="ck_sports_athlete_links_verified",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= created_at", name="ck_sports_athlete_links_end"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id", ondelete="RESTRICT"))
    canonical_competitor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_canonical_competitors.id", ondelete="RESTRICT")
    )
    method: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="declared", server_default="declared")
    established_by: Mapped[str] = mapped_column(String(200))
    evidence_reference: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SportsCanonicalTransfer(TransferTimestamps, Base):
    """An explicit sports graph event; similarity never establishes event identity."""

    __tablename__ = "sports_canonical_transfers"
    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('unknown', 'permanent', 'loan', 'free_transfer', "
            "'loan_return', 'release', 'other')",
            name="ck_sports_transfers_type",
        ),
        CheckConstraint(
            "status IN ('unknown', 'reported', 'confirmed', 'cancelled')",
            name="ck_sports_transfers_status",
        ),
        CheckConstraint("fee_amount IS NULL OR fee_amount >= 0", name="ck_sports_transfers_fee"),
        CheckConstraint(
            "fee_currency IS NULL OR fee_currency ~ '^[A-Z]{3}$'",
            name="ck_sports_transfers_currency",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_canonical_competitors.id", ondelete="RESTRICT"), index=True
    )
    from_club_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sports_canonical_competitors.id", ondelete="RESTRICT"), index=True
    )
    to_club_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sports_canonical_competitors.id", ondelete="RESTRICT"), index=True
    )
    season_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sports_seasons.id", ondelete="RESTRICT"), index=True
    )
    movement_date: Mapped[date | None] = mapped_column(Date, index=True)
    movement_type: Mapped[str] = mapped_column(
        String(20), default="unknown", server_default="unknown"
    )
    status: Mapped[str] = mapped_column(String(20), default="unknown", server_default="unknown")
    display_type: Mapped[str | None] = mapped_column(String(200))
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    fee_currency: Mapped[str | None] = mapped_column(String(3))


class SportsTransferObservation(TransferTimestamps, Base):
    """Latest provider snapshot, independent of optional explicit graph resolution."""

    __tablename__ = "sports_transfer_observations"
    __table_args__ = (
        UniqueConstraint("source_id", "observation_key", name="uq_sports_transfers_observation"),
        UniqueConstraint("source_id", "external_id", name="uq_sports_transfers_external"),
        CheckConstraint(
            "length(btrim(athlete_external_id)) > 0", name="ck_sports_transfer_observations_athlete"
        ),
        CheckConstraint(
            "length(btrim(observation_key)) > 0 AND "
            "((external_id IS NOT NULL AND length(btrim(external_id)) > 0) OR "
            "(external_id IS NULL AND record_reference IS NOT NULL "
            "AND length(btrim(record_reference)) > 0))",
            name="ck_sports_transfer_observations_identity",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_data_sources.id", ondelete="RESTRICT"), index=True
    )
    observation_key: Mapped[str] = mapped_column(String(100))
    external_id: Mapped[str | None] = mapped_column(String(160))
    record_reference: Mapped[str | None] = mapped_column(String(500))
    athlete_external_id: Mapped[str] = mapped_column(String(160))
    athlete_name: Mapped[str | None] = mapped_column(String(200))
    athlete_competitor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sports_competitors.id", ondelete="RESTRICT"), index=True
    )
    canonical_transfer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sports_canonical_transfers.id", ondelete="RESTRICT"), index=True
    )
    from_team_external_id: Mapped[str | None] = mapped_column(String(160))
    from_team_name: Mapped[str | None] = mapped_column(String(200))
    to_team_external_id: Mapped[str | None] = mapped_column(String(160))
    to_team_name: Mapped[str | None] = mapped_column(String(200))
    reported_date: Mapped[date | None] = mapped_column(Date)
    reported_type: Mapped[str | None] = mapped_column(String(200))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
