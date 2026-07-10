"""Create sport events and registrations.

Revision ID: 20260710_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260710_0002"
down_revision: str | None = "20260710_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    status = sa.Enum("registered", "cancelled", name="registration_status")
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "sport_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "organizer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("location", sa.String(240), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("ends_at > starts_at", name="ck_events_date_order"),
        sa.CheckConstraint("capacity > 0", name="ck_events_capacity_positive"),
    )
    op.create_index("ix_events_sport_id", "events", ["sport_id"])
    op.create_index("ix_events_organizer_id", "events", ["organizer_id"])
    op.create_index("ix_events_starts_at", "events", ["starts_at"])
    op.create_table(
        "event_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", status, nullable=False, server_default="registered"),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_registration_user"),
    )
    op.create_index("ix_event_registrations_event_id", "event_registrations", ["event_id"])
    op.create_index("ix_event_registrations_user_id", "event_registrations", ["user_id"])


def downgrade() -> None:
    op.drop_table("event_registrations")
    op.drop_table("events")
    sa.Enum(name="registration_status").drop(op.get_bind())
