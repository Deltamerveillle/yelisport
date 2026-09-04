"""Create SMS Connect transition audit events.

Revision ID: 20260904_0021
Revises: 20260904_0020
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260904_0021"
down_revision = "20260904_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_connect_interest_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "interest_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "actor_role",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "from_status",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "to_status",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "note",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["interest_id"],
            ["sms_connect_interests.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_sms_connect_interest_events_interest_id",
        "sms_connect_interest_events",
        ["interest_id"],
        unique=False,
    )

    op.create_index(
        "ix_sms_connect_interest_events_actor_user_id",
        "sms_connect_interest_events",
        ["actor_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sms_connect_interest_events_actor_user_id",
        table_name="sms_connect_interest_events",
    )

    op.drop_index(
        "ix_sms_connect_interest_events_interest_id",
        table_name="sms_connect_interest_events",
    )

    op.drop_table(
        "sms_connect_interest_events"
    )
