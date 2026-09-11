"""Add canonical SMS24 competitions, competitors and seasons.

Revision ID: 20260910_0028
Revises: 20260910_0027
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260910_0028"
down_revision = "20260910_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sports_canonical_competitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sport_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["sport_id"], ["sports.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_key", name="uq_sports_canonical_competitions_key"),
    )
    op.create_index(
        "ix_sports_canonical_competitions_sport_id", "sports_canonical_competitions", ["sport_id"]
    )
    op.create_index(
        "ix_sports_canonical_competitions_lookup",
        "sports_canonical_competitions",
        ["sport_id", "normalized_name", "country_code"],
    )
    op.create_table(
        "sports_canonical_competitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sport_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_key", sa.String(length=100), nullable=False),
        sa.Column("competitor_type", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["sport_id"], ["sports.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_key", name="uq_sports_canonical_competitors_key"),
        sa.CheckConstraint(
            "competitor_type IN ('team', 'athlete', 'pair', 'selection', 'other')",
            name="ck_sports_canonical_competitors_type",
        ),
    )
    op.create_index(
        "ix_sports_canonical_competitors_sport_id", "sports_canonical_competitors", ["sport_id"]
    )
    op.create_index(
        "ix_sports_canonical_competitors_lookup",
        "sports_canonical_competitors",
        ["sport_id", "competitor_type", "normalized_name", "country_code"],
    )
    op.create_table(
        "sports_seasons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_competition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=40), nullable=False),
        sa.Column("normalized_label", sa.String(length=40), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["canonical_competition_id"],
            ["sports_canonical_competitions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_competition_id",
            "normalized_label",
            name="uq_sports_seasons_competition_label",
        ),
    )
    op.create_index(
        "ix_sports_seasons_canonical_competition_id",
        "sports_seasons",
        ["canonical_competition_id"],
    )
    op.add_column(
        "sports_competitions",
        sa.Column("canonical_competition_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_sports_competitions_canonical_competition_id",
        "sports_competitions",
        "sports_canonical_competitions",
        ["canonical_competition_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_sports_competitions_canonical_competition_id",
        "sports_competitions",
        ["canonical_competition_id"],
    )
    op.add_column(
        "sports_competitors",
        sa.Column("canonical_competitor_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_sports_competitors_canonical_competitor_id",
        "sports_competitors",
        "sports_canonical_competitors",
        ["canonical_competitor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_sports_competitors_canonical_competitor_id",
        "sports_competitors",
        ["canonical_competitor_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sports_competitors_canonical_competitor_id",
        table_name="sports_competitors",
    )
    op.drop_constraint(
        "fk_sports_competitors_canonical_competitor_id",
        "sports_competitors",
        type_="foreignkey",
    )
    op.drop_column("sports_competitors", "canonical_competitor_id")
    op.drop_index(
        "ix_sports_competitions_canonical_competition_id",
        table_name="sports_competitions",
    )
    op.drop_constraint(
        "fk_sports_competitions_canonical_competition_id",
        "sports_competitions",
        type_="foreignkey",
    )
    op.drop_column("sports_competitions", "canonical_competition_id")
    op.drop_index("ix_sports_seasons_canonical_competition_id", table_name="sports_seasons")
    op.drop_table("sports_seasons")
    op.drop_index(
        "ix_sports_canonical_competitors_lookup",
        table_name="sports_canonical_competitors",
    )
    op.drop_index(
        "ix_sports_canonical_competitors_sport_id",
        table_name="sports_canonical_competitors",
    )
    op.drop_table("sports_canonical_competitors")
    op.drop_index(
        "ix_sports_canonical_competitions_lookup",
        table_name="sports_canonical_competitions",
    )
    op.drop_index(
        "ix_sports_canonical_competitions_sport_id",
        table_name="sports_canonical_competitions",
    )
    op.drop_table("sports_canonical_competitions")
