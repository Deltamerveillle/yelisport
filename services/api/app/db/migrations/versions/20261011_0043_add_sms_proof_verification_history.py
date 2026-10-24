"""Add SMS Proof verification history without changing existing performances."""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261011_0043"
down_revision = "20260927_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athlete_performance_verifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        ),
        sa.Column(
            "performance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "athlete_performances.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "verifier_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "decision",
            sa.String(30),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(),  # type: ignore[no-untyped-call]
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "decision IN ('declared', 'documented', 'verified')",
            name="ck_sms_proof_verification_decision",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) > 0",
            name="ck_sms_proof_verification_reason",
        ),
    )

    op.create_index(
        "ix_sms_proof_verifications_performance",
        "athlete_performance_verifications",
        ["performance_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sms_proof_verifications_performance",
        table_name="athlete_performance_verifications",
    )
    op.drop_table("athlete_performance_verifications")
