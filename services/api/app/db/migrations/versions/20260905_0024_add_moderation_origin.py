"""Add moderation case origin and publication-review deduplication.

Revision ID: 20260905_0024
Revises: 20260905_0023
"""

from alembic import op
import sqlalchemy as sa


revision = "20260905_0024"
down_revision = "20260905_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "moderation_reports",
        sa.Column(
            "origin",
            sa.String(length=30),
            nullable=False,
            server_default="user_report",
        ),
    )

    op.create_check_constraint(
        "ck_moderation_reports_origin",
        "moderation_reports",
        "origin IN ('user_report', 'publication_review')",
    )

    op.create_index(
        "ix_moderation_reports_origin",
        "moderation_reports",
        ["origin"],
        unique=False,
    )

    op.create_index(
        "uq_moderation_open_publication_review",
        "moderation_reports",
        ["resource_type", "resource_id", "origin"],
        unique=True,
        postgresql_where=sa.text(
            "origin = 'publication_review' "
            "AND resource_type = 'discover_video' "
            "AND status IN ('submitted', 'under_review')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_moderation_open_publication_review",
        table_name="moderation_reports",
    )
    op.drop_index(
        "ix_moderation_reports_origin",
        table_name="moderation_reports",
    )
    op.drop_constraint(
        "ck_moderation_reports_origin",
        "moderation_reports",
        type_="check",
    )
    op.drop_column(
        "moderation_reports",
        "origin",
    )
