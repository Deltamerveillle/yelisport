"""create SMS subscriptions

Revision ID: 20260901_0007
Revises: 20260901_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260901_0007"
down_revision: str | None = "20260901_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "plan_code",
            sa.String(length=50),
            server_default="free",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="inactive",
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "provider_customer_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "provider_subscription_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "current_period_start",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "current_period_end",
            sa.DateTime(timezone=True),
            nullable=True,
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_subscriptions_user_id"),
        "subscriptions",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_subscriptions_status"),
        "subscriptions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_subscriptions_status"),
        table_name="subscriptions",
    )
    op.drop_index(
        op.f("ix_subscriptions_user_id"),
        table_name="subscriptions",
    )
    op.drop_table("subscriptions")
