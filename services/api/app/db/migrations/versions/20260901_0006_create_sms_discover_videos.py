"""create SMS Discover videos

Revision ID: 20260901_0006
Revises: 20260901_0005
Create Date: 2026-09-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260901_0006"
down_revision: Union[str, None] = "20260901_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "discover_videos",
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
            "video_url",
            sa.String(length=2048),
            nullable=False,
        ),
        sa.Column(
            "thumbnail_url",
            sa.String(length=2048),
            nullable=True,
        ),
        sa.Column(
            "caption",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "duration_seconds",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "publication_status",
            sa.String(length=30),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "moderation_status",
            sa.String(length=30),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "visibility",
            sa.String(length=30),
            server_default="public",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "view_count",
            sa.Integer(),
            server_default="0",
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
        sa.CheckConstraint(
            "duration_seconds >= 15 AND duration_seconds <= 30",
            name="ck_discover_videos_duration",
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_discover_videos_athlete_id"),
        "discover_videos",
        ["athlete_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_discover_videos_publication_status"),
        "discover_videos",
        ["publication_status"],
        unique=False,
    )

    op.create_index(
        op.f("ix_discover_videos_moderation_status"),
        "discover_videos",
        ["moderation_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_discover_videos_moderation_status"),
        table_name="discover_videos",
    )
    op.drop_index(
        op.f("ix_discover_videos_publication_status"),
        table_name="discover_videos",
    )
    op.drop_index(
        op.f("ix_discover_videos_athlete_id"),
        table_name="discover_videos",
    )
    op.drop_table("discover_videos")
