"""Create multisport athlete performances.

Revision ID: 20260904_0019
Revises: 20260903_0018
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260904_0019"
down_revision = "20260903_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athlete_performances",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "athlete_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "sport_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "discipline",
            sa.String(length=120),
            nullable=True,
        ),
        sa.Column(
            "performance_type",
            sa.String(length=80),
            nullable=True,
        ),
        sa.Column(
            "competition_name",
            sa.String(length=180),
            nullable=True,
        ),
        sa.Column(
            "season",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "performance_date",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "verification_status",
            sa.String(length=30),
            server_default="declared",
            nullable=False,
        ),
        sa.Column(
            "source_name",
            sa.String(length=180),
            nullable=True,
        ),
        sa.Column(
            "source_url",
            sa.Text(),
            nullable=True,
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
        sa.CheckConstraint(
            "verification_status IN "
            "('declared', 'documented', 'verified')",
            name=(
                "ck_athlete_performances_"
                "verification_status"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sport_id"],
            ["sports.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_athlete_performances_athlete_id",
        "athlete_performances",
        ["athlete_id"],
        unique=False,
    )

    op.create_index(
        "ix_athlete_performances_sport_id",
        "athlete_performances",
        ["sport_id"],
        unique=False,
    )

    op.create_index(
        "ix_athlete_performances_performance_date",
        "athlete_performances",
        ["performance_date"],
        unique=False,
    )

    op.create_index(
        "ix_athlete_performances_competition_name",
        "athlete_performances",
        ["competition_name"],
        unique=False,
    )

    op.create_index(
        "ix_athlete_performances_verification_status",
        "athlete_performances",
        ["verification_status"],
        unique=False,
    )

    op.create_index(
        "ix_athlete_performances_athlete_date",
        "athlete_performances",
        ["athlete_id", "performance_date"],
        unique=False,
    )

    op.create_index(
        "ix_athlete_performances_sport_date",
        "athlete_performances",
        ["sport_id", "performance_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_athlete_performances_sport_date",
        table_name="athlete_performances",
    )

    op.drop_index(
        "ix_athlete_performances_athlete_date",
        table_name="athlete_performances",
    )

    op.drop_index(
        "ix_athlete_performances_verification_status",
        table_name="athlete_performances",
    )

    op.drop_index(
        "ix_athlete_performances_competition_name",
        table_name="athlete_performances",
    )

    op.drop_index(
        "ix_athlete_performances_performance_date",
        table_name="athlete_performances",
    )

    op.drop_index(
        "ix_athlete_performances_sport_id",
        table_name="athlete_performances",
    )

    op.drop_index(
        "ix_athlete_performances_athlete_id",
        table_name="athlete_performances",
    )

    op.drop_table("athlete_performances")
