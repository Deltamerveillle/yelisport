"""Add provider-neutral YELENI Pay rail transactions; no historical rewrite.

Revision ID: 20260927_0042
Revises: 20260926_0041
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260927_0042"
down_revision = "20260926_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "yeleni_pay_rail_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "payment_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payment_transactions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rail_code", sa.String(50), nullable=False),
        sa.Column("external_transaction_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="created"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("payment_transaction_id", name="uq_yeleni_rail_payment"),
        sa.UniqueConstraint("rail_code", "external_transaction_id", name="uq_yeleni_rail_external"),
        sa.CheckConstraint("rail_code ~ '^[a-z][a-z0-9-]{0,49}$'", name="ck_yeleni_rail_code"),
        sa.CheckConstraint(
            "status IN ('created', 'pending', 'succeeded', 'failed')", name="ck_yeleni_rail_status"
        ),
        sa.CheckConstraint(
            "external_transaction_id IS NULL OR length(btrim(external_transaction_id)) > 0",
            name="ck_yeleni_rail_external_nonempty",
        ),
    )


def downgrade() -> None:
    op.drop_table("yeleni_pay_rail_transactions")
