"""Add SMS Connect opportunities and independent opportunity audit.

Revision ID: 20260926_0040
Revises: 20260926_0039

No historical backfill: conversion requires a new athlete consent decision.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260926_0040"
down_revision = "20260926_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_connect_opportunities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "interest_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sms_connect_interests.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("interest_id", name="uq_sms_connect_opportunities_interest"),
        sa.CheckConstraint(
            "status IN ('active', 'progressing', 'successful', 'unsuccessful', 'withdrawn')",
            name="ck_sms_connect_opportunity_status",
        ),
        sa.CheckConstraint(
            "(status IN ('active', 'progressing') AND closed_at IS NULL) OR "
            "(status IN ('successful', 'unsuccessful', 'withdrawn') AND closed_at IS NOT NULL)",
            name="ck_sms_connect_opportunity_closed_at",
        ),
    )
    op.create_table(
        "sms_connect_opportunity_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sms_connect_opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(30), nullable=True),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('active', 'progressing', 'successful', 'unsuccessful', 'withdrawn')",
            name="ck_sms_connect_opportunity_event_from",
        ),
        sa.CheckConstraint(
            "to_status IN ('active', 'progressing', 'successful', 'unsuccessful', 'withdrawn')",
            name="ck_sms_connect_opportunity_event_to",
        ),
        sa.CheckConstraint(
            "source IN ('athlete_consent', 'athlete_withdrawal', "
            "'athlete_reactivation', 'sms_admin')",
            name="ck_sms_connect_opportunity_event_source",
        ),
    )
    op.create_index(
        "ix_sms_connect_opportunity_events_opportunity_id",
        "sms_connect_opportunity_events",
        ["opportunity_id"],
    )


def downgrade() -> None:
    op.drop_table("sms_connect_opportunity_events")
    op.drop_table("sms_connect_opportunities")
