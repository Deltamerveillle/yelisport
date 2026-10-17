"""Snapshot purchased payment duration without inventing historical terms.

Revision ID: 20260926_0041
Revises: 20260926_0040

Existing rows remain NULL; new commercial initiations supply a positive duration.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260926_0041"
down_revision = "20260926_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_transactions", sa.Column("duration_days", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_payment_transactions_duration_positive", "payment_transactions", "duration_days > 0"
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_payment_transactions_duration_positive", "payment_transactions", type_="check"
    )
    op.drop_column("payment_transactions", "duration_days")
