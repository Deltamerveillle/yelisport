"""Create SMS Connect professional interest requests.

Revision ID: 20260904_0020
Revises: 20260904_0019
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260904_0020"
down_revision = "20260904_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_connect_interests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "athlete_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "athletes.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "requester_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "requester_role",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "interest_type",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "organization_name",
            sa.String(length=180),
            nullable=False,
        ),
        sa.Column(
            "subject",
            sa.String(length=180),
            nullable=False,
        ),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="submitted",
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "interest_type IN "
            "('trial', 'recruitment', 'contract', "
            "'partnership', 'information')",
            name="ck_sms_connect_interest_type",
        ),
        sa.CheckConstraint(
            "status IN "
            "('submitted', 'under_review', 'approved', "
            "'rejected', 'delivered', 'closed')",
            name="ck_sms_connect_interest_status",
        ),
    )

    op.create_index(
        "ix_sms_connect_interests_athlete_id",
        "sms_connect_interests",
        ["athlete_id"],
    )

    op.create_index(
        "ix_sms_connect_interests_requester_user_id",
        "sms_connect_interests",
        ["requester_user_id"],
    )

    op.create_index(
        "ix_sms_connect_interests_requester_role",
        "sms_connect_interests",
        ["requester_role"],
    )

    op.create_index(
        "ix_sms_connect_interests_interest_type",
        "sms_connect_interests",
        ["interest_type"],
    )

    op.create_index(
        "ix_sms_connect_interests_status",
        "sms_connect_interests",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sms_connect_interests_status",
        table_name="sms_connect_interests",
    )

    op.drop_index(
        "ix_sms_connect_interests_interest_type",
        table_name="sms_connect_interests",
    )

    op.drop_index(
        "ix_sms_connect_interests_requester_role",
        table_name="sms_connect_interests",
    )

    op.drop_index(
        "ix_sms_connect_interests_requester_user_id",
        table_name="sms_connect_interests",
    )

    op.drop_index(
        "ix_sms_connect_interests_athlete_id",
        table_name="sms_connect_interests",
    )

    op.drop_table(
        "sms_connect_interests"
    )
