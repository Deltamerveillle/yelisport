"""create SMS Talent submission items

Revision ID: 20260901_0011
Revises: 20260901_0010
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260901_0011"
down_revision = "20260901_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "talent_submission_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "item_type",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "resource_url",
            sa.String(length=2048),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=200),
            nullable=True,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
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
            ["application_id"],
            ["talent_applications.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_talent_submission_items_application_id",
        "talent_submission_items",
        ["application_id"],
        unique=False,
    )

    op.create_index(
        "ix_talent_submission_items_item_type",
        "talent_submission_items",
        ["item_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_talent_submission_items_item_type",
        table_name="talent_submission_items",
    )
    op.drop_index(
        "ix_talent_submission_items_application_id",
        table_name="talent_submission_items",
    )
    op.drop_table("talent_submission_items")
