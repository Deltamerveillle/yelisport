"""Add athlete response state to SMS Connect interests.

Revision ID: 20260926_0039
Revises: 20260922_0038
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260926_0039"
down_revision = "20260922_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sms_connect_interests",
        sa.Column(
            "athlete_response",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "sms_connect_interests",
        sa.Column(
            "athlete_responded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_sms_connect_athlete_response",
        "sms_connect_interests",
        "athlete_response IN ('pending', 'interested', 'declined')",
    )
    op.create_index(
        "ix_sms_connect_interests_athlete_response",
        "sms_connect_interests",
        ["athlete_response"],
        unique=False,
    )

    # Athlete decisions are not administrative from_status/to_status transitions.
    op.create_table(
        "sms_connect_athlete_response_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "interest_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sms_connect_interests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_response", sa.String(30), nullable=False),
        sa.Column("to_response", sa.String(30), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "from_response IN ('pending', 'interested', 'declined')",
            name="ck_sms_connect_response_event_from",
        ),
        sa.CheckConstraint(
            "to_response IN ('interested', 'declined')", name="ck_sms_connect_response_event_to"
        ),
        sa.CheckConstraint(
            "from_response <> to_response", name="ck_sms_connect_response_event_changed"
        ),
    )
    op.create_index(
        "ix_sms_connect_athlete_response_events_interest_id",
        "sms_connect_athlete_response_events",
        ["interest_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("sms_connect_athlete_response_events")
    op.drop_index(
        "ix_sms_connect_interests_athlete_response",
        table_name="sms_connect_interests",
    )
    op.drop_constraint(
        "ck_sms_connect_athlete_response",
        "sms_connect_interests",
        type_="check",
    )
    op.drop_column(
        "sms_connect_interests",
        "athlete_responded_at",
    )
    op.drop_column(
        "sms_connect_interests",
        "athlete_response",
    )
