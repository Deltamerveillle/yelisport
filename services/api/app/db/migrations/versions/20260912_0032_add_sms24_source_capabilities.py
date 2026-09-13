"""Add explicit SMS24 data-source capabilities.

Revision ID: 20260912_0032
Revises: 20260912_0031
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260912_0032"
down_revision = "20260912_0031"
branch_labels = None
depends_on = None


CAPABILITIES = (
    "fixtures",
    "live",
    "standings",
    "news",
    "transfers",
    "injuries",
    "selections",
    "statistics",
)


def upgrade() -> None:
    op.create_table(
        "sports_data_source_capabilities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "capability",
            sa.String(40),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="100",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sports_data_sources.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "source_id",
            "capability",
            name="uq_sports_data_source_capability",
        ),
        sa.CheckConstraint(
            "priority >= 0",
            name="ck_sports_data_source_capabilities_priority_nonnegative",
        ),
        sa.CheckConstraint(
            "capability IN ("
            "'fixtures',"
            "'live',"
            "'standings',"
            "'news',"
            "'transfers',"
            "'injuries',"
            "'selections',"
            "'statistics'"
            ")",
            name="ck_sports_data_source_capabilities_capability",
        ),
    )

    op.create_index(
        "ix_sports_data_source_capabilities_source_id",
        "sports_data_source_capabilities",
        ["source_id"],
    )
    op.create_index(
        "ix_sports_data_source_capabilities_lookup",
        "sports_data_source_capabilities",
        ["capability", "is_active", "priority"],
    )

    bind = op.get_bind()

    rows = bind.execute(
        sa.text(
            """
            SELECT id, slug, priority
            FROM sports_data_sources
            WHERE slug IN ('api-football', 'sportmonks')
            """
        )
    ).mappings()

    for row in rows:
        for capability in (
            "fixtures",
            "live",
            "standings",
        ):
            bind.execute(
                sa.text(
                    """
                    INSERT INTO sports_data_source_capabilities
                        (
                            id,
                            source_id,
                            capability,
                            priority,
                            is_active
                        )
                    VALUES
                        (
                            :id,
                            :source_id,
                            :capability,
                            :priority,
                            true
                        )
                    ON CONFLICT (source_id, capability)
                    DO NOTHING
                    """
                ),
                {
                    "id": uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        (
                            "sms24:source-capability:"
                            f"{row['slug']}:{capability}"
                        ),
                    ),
                    "source_id": row["id"],
                    "capability": capability,
                    "priority": row["priority"],
                },
            )


def downgrade() -> None:
    op.drop_index(
        "ix_sports_data_source_capabilities_lookup",
        table_name="sports_data_source_capabilities",
    )
    op.drop_index(
        "ix_sports_data_source_capabilities_source_id",
        table_name="sports_data_source_capabilities",
    )
    op.drop_table(
        "sports_data_source_capabilities"
    )
