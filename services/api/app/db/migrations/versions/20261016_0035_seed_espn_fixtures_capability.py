"""Enable ESPN fixtures capability for SMS24.

Revision ID: 20261016_0035
Revises: 20261016_0034
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20261016_0035"
down_revision = "20261016_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text("""
            INSERT INTO sports_data_source_capabilities
                (id, source_id, capability, priority, is_active)
            SELECT
                :id, id, 'fixtures', priority, true
            FROM sports_data_sources
            WHERE slug = 'espn'
            ON CONFLICT (source_id, capability) DO NOTHING
        """),
        {
            "id": uuid.uuid5(
                uuid.NAMESPACE_URL,
                "sms24:source-capability:espn:fixtures",
            ),
        },
    )


def downgrade() -> None:
    # Preserve existing source configuration.
    pass
