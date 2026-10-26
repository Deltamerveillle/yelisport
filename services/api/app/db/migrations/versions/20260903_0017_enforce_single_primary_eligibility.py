"""Enforce one primary country eligibility per athlete.

Revision ID: 20260903_0017
Revises: 20260903_0016
"""

import sqlalchemy as sa
from alembic import op

revision = "20260903_0017"
down_revision = "20260903_0016"
branch_labels = None
depends_on = None


INDEX_NAME = "uq_athlete_country_eligibilities_one_primary"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "athlete_country_eligibilities",
        ["athlete_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )


def downgrade() -> None:
    op.drop_index(
        INDEX_NAME,
        table_name="athlete_country_eligibilities",
    )
