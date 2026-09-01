"""create SMS payment transactions

Revision ID: 20260901_0008
Revises: 20260901_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260901_0008"
down_revision: str | None = "20260901_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "reference",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "provider",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "provider_transaction_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "plan_code",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "amount_minor",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="pending",
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
            "amount_minor > 0",
            name="ck_payment_transactions_amount_positive",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reference",
            name="uq_payment_transactions_reference",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_transaction_id",
            name="uq_payment_transactions_provider_transaction",
        ),
    )

    op.create_index(
        op.f("ix_payment_transactions_user_id"),
        "payment_transactions",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_payment_transactions_subscription_id"),
        "payment_transactions",
        ["subscription_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_payment_transactions_status"),
        "payment_transactions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_payment_transactions_status"),
        table_name="payment_transactions",
    )
    op.drop_index(
        op.f("ix_payment_transactions_subscription_id"),
        table_name="payment_transactions",
    )
    op.drop_index(
        op.f("ix_payment_transactions_user_id"),
        table_name="payment_transactions",
    )
    op.drop_table("payment_transactions")
