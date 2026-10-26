"""Add league name to SMS Passport.

Revision ID: 20260903_0018
Revises: 20260903_0017
"""

import sqlalchemy as sa
from alembic import op

revision = "20260903_0018"
down_revision = "20260903_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "athlete_passports",
        sa.Column(
            "league_name",
            sa.String(length=180),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "athlete_passports",
        "league_name",
    )
