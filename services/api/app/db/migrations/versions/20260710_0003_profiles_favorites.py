"""Add complete profiles, settings and favorites.

Revision ID: 20260710_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260710_0003"
down_revision: str | None = "20260710_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("biography", sa.Text()))
    op.add_column("profiles", sa.Column("city", sa.String(120)))
    op.add_column("profiles", sa.Column("country", sa.String(120)))
    op.create_table(
        "user_settings",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("language", sa.String(10), nullable=False, server_default="fr"),
        sa.Column("dark_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _create_favorite_table("favorite_sports", "sport_id", "sports")
    _create_favorite_table("favorite_events", "event_id", "events")


def _create_favorite_table(table: str, target_column: str, target_table: str) -> None:
    op.create_table(
        table,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            target_column,
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{target_table}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", target_column),
    )
    op.create_index(f"ix_{table}_user_id", table, ["user_id"])


def downgrade() -> None:
    op.drop_table("favorite_events")
    op.drop_table("favorite_sports")
    op.drop_table("user_settings")
    op.drop_column("profiles", "country")
    op.drop_column("profiles", "city")
    op.drop_column("profiles", "biography")
