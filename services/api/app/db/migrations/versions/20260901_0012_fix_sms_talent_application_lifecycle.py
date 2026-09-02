"""fix SMS Talent application lifecycle

Revision ID: 20260901_0012
Revises: 20260901_0011
"""

from alembic import op
import sqlalchemy as sa


revision = "20260901_0012"
down_revision = "20260901_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "talent_applications",
        "status",
        existing_type=sa.String(length=30),
        server_default="draft",
        existing_nullable=False,
    )

    op.alter_column(
        "talent_applications",
        "submitted_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE talent_applications
        SET status = 'submitted'
        WHERE status = 'draft'
        """
    )

    op.execute(
        """
        UPDATE talent_applications
        SET submitted_at = now()
        WHERE submitted_at IS NULL
        """
    )

    op.alter_column(
        "talent_applications",
        "submitted_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    op.alter_column(
        "talent_applications",
        "status",
        existing_type=sa.String(length=30),
        server_default="submitted",
        existing_nullable=False,
    )
