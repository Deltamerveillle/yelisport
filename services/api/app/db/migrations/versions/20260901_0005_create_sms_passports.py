"""Create SMS Passport core.

Revision ID: 20260901_0005
Revises: 20260901_0004
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260901_0005"
down_revision: str | None = "20260901_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athlete_passports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "athlete_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("athletes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("discipline", sa.String(length=120), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("position", sa.String(length=120), nullable=True),
        sa.Column("club_name", sa.String(length=180), nullable=True),
        sa.Column("team_name", sa.String(length=180), nullable=True),
        sa.Column("height_cm", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Integer(), nullable=True),
        sa.Column("dominant_side", sa.String(length=30), nullable=True),
        sa.Column(
            "available_for_opportunities",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("sporting_summary", sa.Text(), nullable=True),
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
        sa.UniqueConstraint(
            "athlete_id",
            name="uq_athlete_passports_athlete_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("athlete_passports")
