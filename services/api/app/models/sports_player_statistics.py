"""Provider statistics snapshots; never athlete-owned performance or SMS Proof."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SportsPlayerStatisticObservation(Base):
    __tablename__ = "sports_player_statistic_observations"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_sports_player_stats_external"),
        UniqueConstraint("source_id", "observation_key", name="uq_sports_player_stats_observation"),
        CheckConstraint(
            "length(btrim(athlete_external_id)) > 0", name="ck_sports_player_stats_athlete"
        ),
        CheckConstraint(
            "length(btrim(observation_key)) > 0 AND "
            "((external_id IS NOT NULL AND length(btrim(external_id)) > 0) OR "
            "(external_id IS NULL AND record_reference IS NOT NULL "
            "AND length(btrim(record_reference)) > 0))",
            name="ck_sports_player_stats_identity",
        ),
        CheckConstraint(
            "(record_reference IS NULL OR length(btrim(record_reference)) > 0) AND "
            "(fixture_external_id IS NULL OR length(btrim(fixture_external_id)) > 0)",
            name="ck_sports_player_stats_references",
        ),
        CheckConstraint(
            "scope IN ('unknown', 'fixture', 'season', 'competition', 'career', 'other')",
            name="ck_sports_player_stats_scope",
        ),
        CheckConstraint(
            "jsonb_typeof(metrics_json) = 'object'", name="ck_sports_player_stats_metrics_object"
        ),
        CheckConstraint(
            "jsonb_typeof(metadata_json) = 'object'", name="ck_sports_player_stats_metadata_object"
        ),
        *(
            Index(f"ix_sports_player_stats_{column}", column)
            for column in (
                "sport_id",
                "source_id",
                "athlete_competitor_id",
                "fixture_id",
                "canonical_fixture_id",
                "season_id",
                "fetched_at",
            )
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sport_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sports.id", ondelete="RESTRICT"))
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_data_sources.id", ondelete="RESTRICT"),
    )
    observation_key: Mapped[str] = mapped_column(String(100))
    external_id: Mapped[str | None] = mapped_column(String(160))
    record_reference: Mapped[str | None] = mapped_column(String(500))
    athlete_external_id: Mapped[str] = mapped_column(String(160))
    athlete_name: Mapped[str | None] = mapped_column(String(200))
    athlete_competitor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sports_competitors.id", ondelete="RESTRICT"),
    )
    fixture_external_id: Mapped[str | None] = mapped_column(String(160))
    fixture_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sports_fixtures.id", ondelete="RESTRICT"),
    )
    canonical_fixture_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sports_canonical_fixtures.id", ondelete="RESTRICT"),
    )
    season_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sports_seasons.id", ondelete="RESTRICT"),
    )
    scope: Mapped[str] = mapped_column(String(20), default="unknown", server_default="unknown")
    period_label: Mapped[str | None] = mapped_column(String(100))
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
