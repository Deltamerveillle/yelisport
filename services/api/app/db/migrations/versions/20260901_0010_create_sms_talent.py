"""Create SMS Talent applications and evaluations.

Revision ID: 20260901_0010
Revises: 20260901_0009
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260901_0010"
down_revision = "20260901_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "talent_applications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "athlete_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "sport_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="submitted",
            nullable=False,
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sport_id"],
            ["sports.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_talent_applications_athlete_id",
        "talent_applications",
        ["athlete_id"],
    )
    op.create_index(
        "ix_talent_applications_user_id",
        "talent_applications",
        ["user_id"],
    )
    op.create_index(
        "ix_talent_applications_sport_id",
        "talent_applications",
        ["sport_id"],
    )
    op.create_index(
        "ix_talent_applications_status",
        "talent_applications",
        ["status"],
    )

    op.create_table(
        "talent_evaluations",
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
            "evaluator_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="assigned",
            nullable=False,
        ),
        sa.Column(
            "scores",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "overall_score",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
        sa.Column(
            "recommendation",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "comments",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "overall_score IS NULL OR "
            "(overall_score >= 0 AND overall_score <= 100)",
            name="ck_talent_evaluations_overall_score_range",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["talent_applications.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evaluator_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "application_id",
            "evaluator_user_id",
            name="uq_talent_evaluations_application_evaluator",
        ),
    )

    op.create_index(
        "ix_talent_evaluations_application_id",
        "talent_evaluations",
        ["application_id"],
    )
    op.create_index(
        "ix_talent_evaluations_evaluator_user_id",
        "talent_evaluations",
        ["evaluator_user_id"],
    )
    op.create_index(
        "ix_talent_evaluations_status",
        "talent_evaluations",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_talent_evaluations_status",
        table_name="talent_evaluations",
    )
    op.drop_index(
        "ix_talent_evaluations_evaluator_user_id",
        table_name="talent_evaluations",
    )
    op.drop_index(
        "ix_talent_evaluations_application_id",
        table_name="talent_evaluations",
    )
    op.drop_table("talent_evaluations")

    op.drop_index(
        "ix_talent_applications_status",
        table_name="talent_applications",
    )
    op.drop_index(
        "ix_talent_applications_sport_id",
        table_name="talent_applications",
    )
    op.drop_index(
        "ix_talent_applications_user_id",
        table_name="talent_applications",
    )
    op.drop_index(
        "ix_talent_applications_athlete_id",
        table_name="talent_applications",
    )
    op.drop_table("talent_applications")
