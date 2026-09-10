"""Add provider-independent canonical SMS24 fixture identity.

Revision ID: 20260910_0027
Revises: 20260909_0026
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260910_0027"
down_revision = "20260909_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sports_canonical_fixtures",
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
            "canonical_key",
            sa.String(length=80),
            nullable=False,
        ),
        sa.Column(
            "participant_signature",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "starts_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
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
            ["sport_id"],
            ["sports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_key",
            name="uq_sports_canonical_fixtures_key",
        ),
    )

    op.create_index(
        "ix_sports_canonical_fixtures_sport_id",
        "sports_canonical_fixtures",
        ["sport_id"],
        unique=False,
    )
    op.create_index(
        "ix_sports_canonical_fixtures_starts_at",
        "sports_canonical_fixtures",
        ["starts_at"],
        unique=False,
    )
    op.create_index(
        "ix_sports_canonical_fixtures_lookup",
        "sports_canonical_fixtures",
        [
            "sport_id",
            "participant_signature",
            "starts_at",
        ],
        unique=False,
    )

    op.add_column(
        "sports_fixtures",
        sa.Column(
            "canonical_fixture_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_sports_fixtures_canonical_fixture_id",
        "sports_fixtures",
        "sports_canonical_fixtures",
        ["canonical_fixture_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_sports_fixtures_canonical_fixture_id",
        "sports_fixtures",
        ["canonical_fixture_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sports_fixtures_canonical_fixture_id",
        table_name="sports_fixtures",
    )
    op.drop_constraint(
        "fk_sports_fixtures_canonical_fixture_id",
        "sports_fixtures",
        type_="foreignkey",
    )
    op.drop_column(
        "sports_fixtures",
        "canonical_fixture_id",
    )

    op.drop_index(
        "ix_sports_canonical_fixtures_lookup",
        table_name="sports_canonical_fixtures",
    )
    op.drop_index(
        "ix_sports_canonical_fixtures_starts_at",
        table_name="sports_canonical_fixtures",
    )
    op.drop_index(
        "ix_sports_canonical_fixtures_sport_id",
        table_name="sports_canonical_fixtures",
    )
    op.drop_table("sports_canonical_fixtures")
