"""Register ESPN as an SMS24 sports data source.

Revision ID: 20261016_0034
Revises: 20260913_0033
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20261016_0034"
down_revision = "20260913_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    slug = "espn"

    op.get_bind().execute(
        sa.text("""
            INSERT INTO sports_data_sources
                (id, slug, name, provider_type, priority, is_active, health_status)
            VALUES
                (:id, :slug, :name, 'api', :priority, true, 'unavailable')
            ON CONFLICT (slug) DO NOTHING
        """),
        {
            "id": uuid.uuid5(uuid.NAMESPACE_URL, f"sms24:source:{slug}"),
            "slug": slug,
            "name": "ESPN",
            "priority": 30,
        },
    )


def downgrade() -> None:
    # Preserve existing fixtures and their source references.
    pass
