"""Source-specific standings linked to existing canonical season and competitor identities."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SportsStanding(Base):
    __tablename__ = "sports_standings"
    __table_args__ = (
        CheckConstraint("position >= 1", name="ck_sports_standings_position_positive"),
        UniqueConstraint(
            "source_id",
            "season_id",
            "canonical_competitor_id",
            "stage_external_id",
            "group_scope",
            name="uq_sports_standings_observation",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_data_sources.id", ondelete="RESTRICT"),
        index=True,
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_seasons.id", ondelete="CASCADE"),
        index=True,
    )
    canonical_competitor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_canonical_competitors.id", ondelete="RESTRICT"),
        index=True,
    )
    external_competitor_id: Mapped[str | None] = mapped_column(String(160))
    position: Mapped[int] = mapped_column(Integer)
    points: Mapped[int | None] = mapped_column(Integer)
    played: Mapped[int | None] = mapped_column(Integer)
    wins: Mapped[int | None] = mapped_column(Integer)
    draws: Mapped[int | None] = mapped_column(Integer)
    losses: Mapped[int | None] = mapped_column(Integer)
    goals_for: Mapped[int | None] = mapped_column(Integer)
    goals_against: Mapped[int | None] = mapped_column(Integer)
    goal_difference: Mapped[int | None] = mapped_column(Integer)
    home_played: Mapped[int | None] = mapped_column(Integer)
    home_wins: Mapped[int | None] = mapped_column(Integer)
    home_draws: Mapped[int | None] = mapped_column(Integer)
    home_losses: Mapped[int | None] = mapped_column(Integer)
    home_goals_for: Mapped[int | None] = mapped_column(Integer)
    home_goals_against: Mapped[int | None] = mapped_column(Integer)
    home_points: Mapped[int | None] = mapped_column(Integer)
    away_played: Mapped[int | None] = mapped_column(Integer)
    away_wins: Mapped[int | None] = mapped_column(Integer)
    away_draws: Mapped[int | None] = mapped_column(Integer)
    away_losses: Mapped[int | None] = mapped_column(Integer)
    away_goals_for: Mapped[int | None] = mapped_column(Integer)
    away_goals_against: Mapped[int | None] = mapped_column(Integer)
    away_points: Mapped[int | None] = mapped_column(Integer)
    external_id: Mapped[str | None] = mapped_column(String(160))
    external_competition_id: Mapped[str | None] = mapped_column(String(160))
    external_season_id: Mapped[str | None] = mapped_column(String(160))
    form: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    movement_status: Mapped[str | None] = mapped_column(String(80))
    stage_external_id: Mapped[str | None] = mapped_column(String(160))
    group_external_id: Mapped[str | None] = mapped_column(String(160))
    group_name: Mapped[str | None] = mapped_column(String(240))
    round_external_id: Mapped[str | None] = mapped_column(String(160))
    standing_rule_external_id: Mapped[str | None] = mapped_column(String(160))
    group_scope: Mapped[str] = mapped_column(
        Text,
        Computed(
            "CASE WHEN group_external_id IS NOT NULL THEN 'id:' || group_external_id "
            "WHEN group_name IS NOT NULL THEN 'name:' || "
            "lower(regexp_replace(group_name, '^[[:space:]]+|[[:space:]]+$', '', 'g')) "
            "ELSE 'none:' END",
            persisted=True,
        ),
        nullable=False,
    )
    provider_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
