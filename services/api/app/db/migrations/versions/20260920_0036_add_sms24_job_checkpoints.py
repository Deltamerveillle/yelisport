"""Add technical SMS24 job checkpoints; no jobs or capabilities are seeded.

Revision ID: 20260920_0036
Revises: 20260920_0035
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260920_0036"
down_revision = "20260920_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms24_job_checkpoints",
        sa.Column("job_key", sa.String(160), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="idle"),
        sa.Column("reference_date", sa.Date(), nullable=True),
        sa.Column(
            "cursor",
            postgresql.JSONB(),  # type: ignore[no-untyped-call]
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "parameters",
            postgresql.JSONB(),  # type: ignore[no-untyped-call]
            nullable=False,
            server_default="{}",
        ),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("length(job_key) > 0", name="ck_sms24_job_key"),
        sa.CheckConstraint(
            "status IN ('idle', 'running', 'completed', 'completed_with_errors')",
            name="ck_sms24_job_status",
        ),
        sa.CheckConstraint("jsonb_typeof(cursor) = 'object'", name="ck_sms24_job_cursor"),
        sa.CheckConstraint("jsonb_typeof(parameters) = 'object'", name="ck_sms24_job_parameters"),
        sa.CheckConstraint("failed_attempts >= 0", name="ck_sms24_job_failed_attempts"),
        sa.CheckConstraint(
            "(status = 'idle' AND reference_date IS NULL AND started_at IS NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'running' AND reference_date IS NOT NULL AND started_at IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(status IN ('completed', 'completed_with_errors') AND reference_date IS NOT NULL "
            "AND started_at IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_sms24_job_lifecycle",
        ),
    )


def downgrade() -> None:
    op.drop_table("sms24_job_checkpoints")
