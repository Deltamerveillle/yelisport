"""Add SMS24 transfer events, provider observations, and explicit athlete links.

Revision ID: 20260916_0034
Revises: 20260913_0033

No identity backfill, capability activation, or modification of existing profiles.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260916_0034"
down_revision = "20260913_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sports_athlete_identity_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("athlete_id", sa.UUID(), nullable=False),
        sa.Column("canonical_competitor_id", sa.UUID(), nullable=False),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="declared", nullable=False),
        sa.Column("established_by", sa.String(length=200), nullable=False),
        sa.Column("evidence_reference", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
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
            "method IN ('athlete_claim', 'manual_review', 'institutional_review')",
            name="ck_sports_athlete_links_method",
        ),
        sa.CheckConstraint(
            "status != 'verified' OR (method = 'institutional_review' AND verified_at IS NOT NULL)",
            name="ck_sports_athlete_links_verified",
        ),
        sa.CheckConstraint(
            "status IN ('declared', 'documented', 'verified')",
            name="ck_sports_athlete_links_status",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= created_at", name="ck_sports_athlete_links_end"
        ),
        sa.CheckConstraint(
            "length(btrim(established_by)) > 0 AND length(btrim(evidence_reference)) > 0",
            name="ck_sports_athlete_links_provenance",
        ),
        sa.ForeignKeyConstraint(["athlete_id"], ["athletes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["canonical_competitor_id"], ["sports_canonical_competitors.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_sports_athlete_links_active_athlete",
        "sports_athlete_identity_links",
        ["athlete_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_index(
        "uq_sports_athlete_links_active_competitor",
        "sports_athlete_identity_links",
        ["canonical_competitor_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_table(
        "sports_canonical_transfers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("canonical_athlete_id", sa.UUID(), nullable=False),
        sa.Column("from_club_id", sa.UUID(), nullable=True),
        sa.Column("to_club_id", sa.UUID(), nullable=True),
        sa.Column("season_id", sa.UUID(), nullable=True),
        sa.Column("movement_date", sa.Date(), nullable=True),
        sa.Column("movement_type", sa.String(length=20), server_default="unknown", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="unknown", nullable=False),
        sa.Column("display_type", sa.String(length=200), nullable=True),
        sa.Column("fee_amount", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("fee_currency", sa.String(length=3), nullable=True),
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
            "fee_currency IS NULL OR fee_currency ~ '^[A-Z]{3}$'",
            name="ck_sports_transfers_currency",
        ),
        sa.CheckConstraint(
            "movement_type IN ('unknown', 'permanent', 'loan', 'free_transfer', "
            "'loan_return', 'release', 'other')",
            name="ck_sports_transfers_type",
        ),
        sa.CheckConstraint(
            "status IN ('unknown', 'reported', 'confirmed', 'cancelled')",
            name="ck_sports_transfers_status",
        ),
        sa.CheckConstraint("fee_amount IS NULL OR fee_amount >= 0", name="ck_sports_transfers_fee"),
        sa.ForeignKeyConstraint(
            ["canonical_athlete_id"], ["sports_canonical_competitors.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["from_club_id"], ["sports_canonical_competitors.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["season_id"], ["sports_seasons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["to_club_id"], ["sports_canonical_competitors.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sports_canonical_transfers_canonical_athlete_id"),
        "sports_canonical_transfers",
        ["canonical_athlete_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_canonical_transfers_from_club_id"),
        "sports_canonical_transfers",
        ["from_club_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_canonical_transfers_movement_date"),
        "sports_canonical_transfers",
        ["movement_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_canonical_transfers_season_id"),
        "sports_canonical_transfers",
        ["season_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_canonical_transfers_to_club_id"),
        "sports_canonical_transfers",
        ["to_club_id"],
        unique=False,
    )
    op.create_table(
        "sports_transfer_observations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("observation_key", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=160), nullable=True),
        sa.Column("record_reference", sa.String(length=500), nullable=True),
        sa.Column("athlete_external_id", sa.String(length=160), nullable=False),
        sa.Column("athlete_name", sa.String(length=200), nullable=True),
        sa.Column("athlete_competitor_id", sa.UUID(), nullable=True),
        sa.Column("canonical_transfer_id", sa.UUID(), nullable=True),
        sa.Column("from_team_external_id", sa.String(length=160), nullable=True),
        sa.Column("from_team_name", sa.String(length=200), nullable=True),
        sa.Column("to_team_external_id", sa.String(length=160), nullable=True),
        sa.Column("to_team_name", sa.String(length=200), nullable=True),
        sa.Column("reported_date", sa.Date(), nullable=True),
        sa.Column("reported_type", sa.String(length=200), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(),  # type: ignore[no-untyped-call]
            server_default="{}",
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
            "length(btrim(athlete_external_id)) > 0", name="ck_sports_transfer_observations_athlete"
        ),
        sa.CheckConstraint(
            "length(btrim(observation_key)) > 0 AND "
            "((external_id IS NOT NULL AND length(btrim(external_id)) > 0) OR "
            "(external_id IS NULL AND record_reference IS NOT NULL "
            "AND length(btrim(record_reference)) > 0))",
            name="ck_sports_transfer_observations_identity",
        ),
        sa.ForeignKeyConstraint(
            ["athlete_competitor_id"], ["sports_competitors.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["canonical_transfer_id"], ["sports_canonical_transfers.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sports_data_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "external_id", name="uq_sports_transfers_external"),
        sa.UniqueConstraint("source_id", "observation_key", name="uq_sports_transfers_observation"),
    )
    op.create_index(
        op.f("ix_sports_transfer_observations_athlete_competitor_id"),
        "sports_transfer_observations",
        ["athlete_competitor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_transfer_observations_canonical_transfer_id"),
        "sports_transfer_observations",
        ["canonical_transfer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_transfer_observations_fetched_at"),
        "sports_transfer_observations",
        ["fetched_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_transfer_observations_source_id"),
        "sports_transfer_observations",
        ["source_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("sports_transfer_observations")
    op.drop_table("sports_canonical_transfers")
    op.drop_table("sports_athlete_identity_links")
