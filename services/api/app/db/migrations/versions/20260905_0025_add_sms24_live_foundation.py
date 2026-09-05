"""add sms24 live foundation

Revision ID: 20260905_0025
Revises: 20260905_0024
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260905_0025"
down_revision: Union[str, None] = "20260905_0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sports_data_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "provider_type",
            sa.String(length=40),
            server_default=sa.text("'api'"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            server_default=sa.text("100"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "health_status",
            sa.String(length=20),
            server_default=sa.text("'healthy'"),
            nullable=False,
        ),
        sa.Column(
            "last_success_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_failure_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
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
            "health_status IN ('healthy', 'degraded', 'unavailable')",
            name="ck_sports_data_sources_health_status",
        ),
        sa.CheckConstraint(
            "priority >= 0",
            name="ck_sports_data_sources_priority_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_sports_data_sources_health_status",
        "sports_data_sources",
        ["health_status"],
        unique=False,
    )
    op.create_index(
        "ix_sports_data_sources_is_active",
        "sports_data_sources",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        "ix_sports_data_sources_priority",
        "sports_data_sources",
        ["priority"],
        unique=False,
    )
    op.create_index(
        "ix_sports_data_sources_slug",
        "sports_data_sources",
        ["slug"],
        unique=True,
    )

    op.create_table(
        "sports_competitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "sport_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("season", sa.String(length=40), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "source_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sports_data_sources.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sport_id"],
            ["sports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "external_id",
            name="uq_sports_competitions_source_external",
        ),
    )

    for name, columns in (
        ("ix_sports_competitions_country_code", ["country_code"]),
        ("ix_sports_competitions_fetched_at", ["fetched_at"]),
        ("ix_sports_competitions_is_active", ["is_active"]),
        ("ix_sports_competitions_name", ["name"]),
        ("ix_sports_competitions_season", ["season"]),
        ("ix_sports_competitions_source_id", ["source_id"]),
        ("ix_sports_competitions_sport_id", ["sport_id"]),
    ):
        op.create_index(name, "sports_competitions", columns, unique=False)

    op.create_table(
        "sports_competitors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "sport_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=160), nullable=False),
        sa.Column(
            "competitor_type",
            sa.String(length=20),
            server_default=sa.text("'team'"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("short_name", sa.String(length=100), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "source_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
            "competitor_type IN "
            "('team', 'athlete', 'pair', 'selection', 'other')",
            name="ck_sports_competitors_type",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sports_data_sources.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sport_id"],
            ["sports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "external_id",
            name="uq_sports_competitors_source_external",
        ),
    )

    for name, columns in (
        ("ix_sports_competitors_competitor_type", ["competitor_type"]),
        ("ix_sports_competitors_country_code", ["country_code"]),
        ("ix_sports_competitors_fetched_at", ["fetched_at"]),
        ("ix_sports_competitors_name", ["name"]),
        ("ix_sports_competitors_source_id", ["source_id"]),
        ("ix_sports_competitors_sport_id", ["sport_id"]),
    ):
        op.create_index(name, "sports_competitors", columns, unique=False)

    op.create_table(
        "sports_fixtures",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "sport_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "competition_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("external_id", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=True),
        sa.Column(
            "starts_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'scheduled'"),
            nullable=False,
        ),
        sa.Column("live_clock", sa.String(length=40), nullable=True),
        sa.Column("venue", sa.String(length=240), nullable=True),
        sa.Column(
            "result_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "source_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
            "status IN ('scheduled', 'live', 'finished', 'postponed', "
            "'cancelled', 'suspended', 'unknown')",
            name="ck_sports_fixtures_status",
        ),
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["sports_competitions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sports_data_sources.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sport_id"],
            ["sports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "external_id",
            name="uq_sports_fixtures_source_external",
        ),
    )

    for name, columns in (
        ("ix_sports_fixtures_competition_id", ["competition_id"]),
        ("ix_sports_fixtures_fetched_at", ["fetched_at"]),
        ("ix_sports_fixtures_source_id", ["source_id"]),
        ("ix_sports_fixtures_source_updated_at", ["source_updated_at"]),
        ("ix_sports_fixtures_sport_id", ["sport_id"]),
        ("ix_sports_fixtures_starts_at", ["starts_at"]),
        ("ix_sports_fixtures_status", ["status"]),
    ):
        op.create_index(name, "sports_fixtures", columns, unique=False)

    op.create_table(
        "sports_fixture_participants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "fixture_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "competitor_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=40), nullable=True),
        sa.Column(
            "score_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "result_status",
            sa.String(length=40),
            nullable=True,
        ),
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
            "position >= 0",
            name="ck_sports_fixture_participants_position_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["competitor_id"],
            ["sports_competitors.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["sports_fixtures.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fixture_id",
            "competitor_id",
            name="uq_sports_fixture_participant",
        ),
    )

    op.create_index(
        "ix_sports_fixture_participants_competitor_id",
        "sports_fixture_participants",
        ["competitor_id"],
        unique=False,
    )
    op.create_index(
        "ix_sports_fixture_participants_fixture_id",
        "sports_fixture_participants",
        ["fixture_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("sports_fixture_participants")
    op.drop_table("sports_fixtures")
    op.drop_table("sports_competitors")
    op.drop_table("sports_competitions")
    op.drop_table("sports_data_sources")
