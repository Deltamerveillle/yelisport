"""Add SMS24 provider player-statistics observation foundation.

Revision ID: 20260921_0037
Revises: 20260920_0036

Provider observations remain separate from athlete-owned AthletePerformance.
No provider capability activation, human identity creation, fuzzy matching,
SMS Proof verification, or AthletePerformance mutation is performed here.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260921_0037"
down_revision = "20260920_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sports_player_statistic_observations",
        sa.Column("id", sa.UUID(), nullable=False),
        # Explicit multisport identity. This remains known even before the
        # provider athlete is explicitly resolved to SportsCompetitor.
        sa.Column("sport_id", sa.UUID(), nullable=False),
        # Provider provenance.
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("observation_key", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=160), nullable=True),
        sa.Column("record_reference", sa.String(length=500), nullable=True),
        # Provider-side athlete identity.
        sa.Column("athlete_external_id", sa.String(length=160), nullable=False),
        sa.Column("athlete_name", sa.String(length=200), nullable=True),
        sa.Column("athlete_competitor_id", sa.UUID(), nullable=True),
        # Explicitly resolved context only.
        # Opaque provider context survives before a local fixture is resolved.
        # It is never used to manufacture an observation identity.
        sa.Column("fixture_external_id", sa.String(length=160), nullable=True),
        sa.Column("fixture_id", sa.UUID(), nullable=True),
        sa.Column("canonical_fixture_id", sa.UUID(), nullable=True),
        sa.Column("season_id", sa.UUID(), nullable=True),
        # Multisport/statistical context.
        sa.Column(
            "scope",
            sa.String(length=20),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column("period_label", sa.String(length=100), nullable=True),
        # Provider-reported metrics. Missing values remain absent/unknown;
        # they must never be manufactured as zero by this schema.
        sa.Column(
            "metrics_json",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(athlete_external_id)) > 0",
            name="ck_sports_player_stats_athlete",
        ),
        sa.CheckConstraint(
            "length(btrim(observation_key)) > 0 AND "
            "((external_id IS NOT NULL AND length(btrim(external_id)) > 0) OR "
            "(external_id IS NULL AND record_reference IS NOT NULL "
            "AND length(btrim(record_reference)) > 0))",
            name="ck_sports_player_stats_identity",
        ),
        sa.CheckConstraint(
            "(record_reference IS NULL OR length(btrim(record_reference)) > 0) AND "
            "(fixture_external_id IS NULL OR length(btrim(fixture_external_id)) > 0)",
            name="ck_sports_player_stats_references",
        ),
        sa.CheckConstraint(
            "scope IN ('unknown', 'fixture', 'season', 'competition', 'career', 'other')",
            name="ck_sports_player_stats_scope",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metrics_json) = 'object'",
            name="ck_sports_player_stats_metrics_object",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metadata_json) = 'object'",
            name="ck_sports_player_stats_metadata_object",
        ),
        sa.ForeignKeyConstraint(
            ["sport_id"],
            ["sports.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sports_data_sources.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["athlete_competitor_id"],
            ["sports_competitors.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["sports_fixtures.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_fixture_id"],
            ["sports_canonical_fixtures.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["sports_seasons.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "external_id",
            name="uq_sports_player_stats_external",
        ),
        sa.UniqueConstraint(
            "source_id",
            "observation_key",
            name="uq_sports_player_stats_observation",
        ),
    )

    op.create_index(
        "ix_sports_player_stats_sport_id",
        "sports_player_statistic_observations",
        ["sport_id"],
        unique=False,
    )
    op.create_index(
        "ix_sports_player_stats_source_id",
        "sports_player_statistic_observations",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_sports_player_stats_athlete_competitor_id",
        "sports_player_statistic_observations",
        ["athlete_competitor_id"],
        unique=False,
    )
    op.create_index(
        "ix_sports_player_stats_fixture_id",
        "sports_player_statistic_observations",
        ["fixture_id"],
        unique=False,
    )
    op.create_index(
        "ix_sports_player_stats_canonical_fixture_id",
        "sports_player_statistic_observations",
        ["canonical_fixture_id"],
        unique=False,
    )
    op.create_index(
        "ix_sports_player_stats_season_id",
        "sports_player_statistic_observations",
        ["season_id"],
        unique=False,
    )
    op.create_index(
        "ix_sports_player_stats_fetched_at",
        "sports_player_statistic_observations",
        ["fetched_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("sports_player_statistic_observations")
