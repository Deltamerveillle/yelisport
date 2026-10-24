"""Store private athlete media metadata without making media public.

Revision ID: 20261023_0045
Revises: 20261023_0044
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20261023_0045"
down_revision = "20261023_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athlete_media",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "athlete_id", UUID(as_uuid=True),
            sa.ForeignKey("athletes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_path", sa.String(length=320), nullable=False),
        sa.Column("media_type", sa.String(length=10), nullable=False),
        sa.Column("mime_type", sa.String(length=40), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "moderation_status", sa.String(length=20),
            server_default="pending", nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("storage_path", name="uq_athlete_media_path"),
    )
    op.create_index("ix_athlete_media_athlete_id", "athlete_media", ["athlete_id"])


def downgrade() -> None:
    op.drop_index("ix_athlete_media_athlete_id", table_name="athlete_media")
    op.drop_table("athlete_media")
