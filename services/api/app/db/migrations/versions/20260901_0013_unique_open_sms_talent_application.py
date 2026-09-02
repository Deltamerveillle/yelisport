"""unique open SMS Talent application per athlete

Revision ID: 20260901_0013
Revises: 20260901_0012
"""

from alembic import op
import sqlalchemy as sa


revision = "20260901_0013"
down_revision = "20260901_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_talent_applications_open_athlete",
        "talent_applications",
        ["athlete_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('draft', 'submitted')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_talent_applications_open_athlete",
        table_name="talent_applications",
    )
