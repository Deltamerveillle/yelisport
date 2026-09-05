"""Create SMS notification projection.

Revision ID: 20260904_0022
Revises: 20260904_0021
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260904_0022"
down_revision = "20260904_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "recipient_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "notification_type",
            sa.String(length=80),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=180),
            nullable=False,
        ),
        sa.Column(
            "body",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=50),
            server_default="sms",
            nullable=False,
        ),
        sa.Column(
            "resource_type",
            sa.String(length=80),
            nullable=True,
        ),
        sa.Column(
            "resource_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "dedupe_key",
            sa.String(length=180),
            nullable=False,
        ),
        sa.Column(
            "is_read",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dedupe_key",
            name="uq_notifications_dedupe_key",
        ),
    )

    op.create_index(
        "ix_notifications_recipient_user_id",
        "notifications",
        ["recipient_user_id"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_notification_type",
        "notifications",
        ["notification_type"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_source",
        "notifications",
        ["source"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_resource_type",
        "notifications",
        ["resource_type"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_resource_id",
        "notifications",
        ["resource_id"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_is_read",
        "notifications",
        ["is_read"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_created_at",
        "notifications",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notifications_created_at",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_is_read",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_resource_id",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_resource_type",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_source",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_notification_type",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_recipient_user_id",
        table_name="notifications",
    )

    op.drop_table("notifications")
