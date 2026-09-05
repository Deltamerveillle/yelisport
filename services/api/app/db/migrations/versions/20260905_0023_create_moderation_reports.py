"""create moderation reports and audit events

Revision ID: 20260905_0023
Revises: 20260904_0022
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260905_0023"
down_revision = "20260904_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moderation_reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "reporter_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "resource_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "resource_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "details",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="submitted",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "resource_type IN "
            "('user', 'athlete', 'discover_video', 'sms_connect_interest')",
            name="ck_moderation_reports_resource_type",
        ),
        sa.CheckConstraint(
            "reason IN "
            "('spam', 'fraud', 'abuse', 'inappropriate_content', "
            "'impersonation', 'safety', 'other')",
            name="ck_moderation_reports_reason",
        ),
        sa.CheckConstraint(
            "status IN "
            "('submitted', 'under_review', 'resolved', 'dismissed')",
            name="ck_moderation_reports_status",
        ),
        sa.ForeignKeyConstraint(
            ["reporter_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_moderation_reports_reporter_user_id",
        "moderation_reports",
        ["reporter_user_id"],
    )
    op.create_index(
        "ix_moderation_reports_resource_type",
        "moderation_reports",
        ["resource_type"],
    )
    op.create_index(
        "ix_moderation_reports_resource_id",
        "moderation_reports",
        ["resource_id"],
    )
    op.create_index(
        "ix_moderation_reports_reason",
        "moderation_reports",
        ["reason"],
    )
    op.create_index(
        "ix_moderation_reports_status",
        "moderation_reports",
        ["status"],
    )
    op.create_index(
        "ix_moderation_reports_created_at",
        "moderation_reports",
        ["created_at"],
    )

    op.create_table(
        "moderation_report_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "report_id",
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
            "action",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "from_status",
            sa.String(length=30),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            sa.String(length=30),
            nullable=True,
        ),
        sa.Column(
            "note",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN "
            "('submitted', 'under_review', 'resolved', 'dismissed', "
            "'discover_approved', 'discover_rejected', "
            "'user_suspended', 'user_reactivated')",
            name="ck_moderation_report_events_action",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["moderation_reports.id"],
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
        "ix_moderation_report_events_report_id",
        "moderation_report_events",
        ["report_id"],
    )
    op.create_index(
        "ix_moderation_report_events_actor_user_id",
        "moderation_report_events",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_moderation_report_events_action",
        "moderation_report_events",
        ["action"],
    )
    op.create_index(
        "ix_moderation_report_events_created_at",
        "moderation_report_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_moderation_report_events_created_at",
        table_name="moderation_report_events",
    )
    op.drop_index(
        "ix_moderation_report_events_action",
        table_name="moderation_report_events",
    )
    op.drop_index(
        "ix_moderation_report_events_actor_user_id",
        table_name="moderation_report_events",
    )
    op.drop_index(
        "ix_moderation_report_events_report_id",
        table_name="moderation_report_events",
    )
    op.drop_table("moderation_report_events")

    op.drop_index(
        "ix_moderation_reports_created_at",
        table_name="moderation_reports",
    )
    op.drop_index(
        "ix_moderation_reports_status",
        table_name="moderation_reports",
    )
    op.drop_index(
        "ix_moderation_reports_reason",
        table_name="moderation_reports",
    )
    op.drop_index(
        "ix_moderation_reports_resource_id",
        table_name="moderation_reports",
    )
    op.drop_index(
        "ix_moderation_reports_resource_type",
        table_name="moderation_reports",
    )
    op.drop_index(
        "ix_moderation_reports_reporter_user_id",
        table_name="moderation_reports",
    )
    op.drop_table("moderation_reports")
