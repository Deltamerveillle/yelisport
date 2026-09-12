"""Add source-specific SMS24 standings observations.

Revision ID: 20260911_0030
Revises: 20260911_0029
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260911_0030"
down_revision = "20260911_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sports_standings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("season_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_competitor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_competitor_id", sa.String(160), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.Column("played", sa.Integer(), nullable=True),
        sa.Column("wins", sa.Integer(), nullable=True),
        sa.Column("draws", sa.Integer(), nullable=True),
        sa.Column("losses", sa.Integer(), nullable=True),
        sa.Column("goals_for", sa.Integer(), nullable=True),
        sa.Column("goals_against", sa.Integer(), nullable=True),
        sa.Column("goal_difference", sa.Integer(), nullable=True),
        sa.Column("home_played", sa.Integer(), nullable=True),
        sa.Column("home_wins", sa.Integer(), nullable=True),
        sa.Column("home_draws", sa.Integer(), nullable=True),
        sa.Column("home_losses", sa.Integer(), nullable=True),
        sa.Column("home_goals_for", sa.Integer(), nullable=True),
        sa.Column("home_goals_against", sa.Integer(), nullable=True),
        sa.Column("home_points", sa.Integer(), nullable=True),
        sa.Column("away_played", sa.Integer(), nullable=True),
        sa.Column("away_wins", sa.Integer(), nullable=True),
        sa.Column("away_draws", sa.Integer(), nullable=True),
        sa.Column("away_losses", sa.Integer(), nullable=True),
        sa.Column("away_goals_for", sa.Integer(), nullable=True),
        sa.Column("away_goals_against", sa.Integer(), nullable=True),
        sa.Column("away_points", sa.Integer(), nullable=True),
        sa.Column("external_id", sa.String(160), nullable=True),
        sa.Column("external_competition_id", sa.String(160), nullable=True),
        sa.Column("external_season_id", sa.String(160), nullable=True),
        sa.Column("form", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("movement_status", sa.String(80), nullable=True),
        sa.Column("stage_external_id", sa.String(160), nullable=True),
        sa.Column("group_external_id", sa.String(160), nullable=True),
        sa.Column("group_name", sa.String(240), nullable=True),
        sa.Column("round_external_id", sa.String(160), nullable=True),
        sa.Column("standing_rule_external_id", sa.String(160), nullable=True),
        sa.Column(
            "group_scope",
            sa.Text(),
            sa.Computed(
                "CASE WHEN group_external_id IS NOT NULL THEN 'id:' || group_external_id "
                "WHEN group_name IS NOT NULL THEN 'name:' || "
                "lower(regexp_replace(group_name, '^[[:space:]]+|[[:space:]]+$', '', 'g')) "
                "ELSE 'none:' END",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["sports_data_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["season_id"], ["sports_seasons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["canonical_competitor_id"], ["sports_canonical_competitors.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("position >= 1", name="ck_sports_standings_position_positive"),
        sa.UniqueConstraint(
            "source_id",
            "season_id",
            "canonical_competitor_id",
            "stage_external_id",
            "group_scope",
            name="uq_sports_standings_observation",
            postgresql_nulls_not_distinct=True,
        ),
    )
    for column in ("source_id", "season_id", "canonical_competitor_id", "fetched_at"):
        op.create_index(f"ix_sports_standings_{column}", "sports_standings", [column])


def downgrade() -> None:
    for column in ("fetched_at", "canonical_competitor_id", "season_id", "source_id"):
        op.drop_index(f"ix_sports_standings_{column}", table_name="sports_standings")
    op.drop_table("sports_standings")
