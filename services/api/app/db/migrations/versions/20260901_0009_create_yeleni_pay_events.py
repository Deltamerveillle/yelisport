"""create YELENI Pay events

Revision ID: 20260901_0009
Revises: 20260901_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260901_0009"
down_revision: str | None = "20260901_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "yeleni_pay_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=80),
            nullable=False,
        ),
        sa.Column(
            "reference",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="received",
            nullable=False,
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            name="uq_yeleni_pay_events_event_id",
        ),
    )

    op.create_index(
        op.f("ix_yeleni_pay_events_event_type"),
        "yeleni_pay_events",
        ["event_type"],
        unique=False,
    )

    op.create_index(
        op.f("ix_yeleni_pay_events_reference"),
        "yeleni_pay_events",
        ["reference"],
        unique=False,
    )

    op.create_index(
        op.f("ix_yeleni_pay_events_status"),
        "yeleni_pay_events",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_yeleni_pay_events_status"),
        table_name="yeleni_pay_events",
    )
    op.drop_index(
        op.f("ix_yeleni_pay_events_reference"),
        table_name="yeleni_pay_events",
    )
    op.drop_index(
        op.f("ix_yeleni_pay_events_event_type"),
        table_name="yeleni_pay_events",
    )
    op.drop_table("yeleni_pay_events")
