"""Populate SMS24 source configuration without changing the storage schema.

Revision ID: 20260909_0026
Revises: 20260905_0025
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20260909_0026"
down_revision = "20260905_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for slug, name, priority in (
        ("api-football", "API-Football", 10),
        ("sportmonks", "Sportmonks", 20),
    ):
        op.get_bind().execute(sa.text("""
            INSERT INTO sports_data_sources
                (id, slug, name, provider_type, priority, is_active, health_status)
            VALUES (:id, :slug, :name, 'api', :priority, true, 'unavailable')
            ON CONFLICT (slug) DO UPDATE
            SET name = EXCLUDED.name, priority = EXCLUDED.priority
        """), {
            "id": uuid.uuid5(uuid.NAMESPACE_URL, f"sms24:source:{slug}"),
            "slug": slug, "name": name, "priority": priority,
        })


def downgrade() -> None:
    # Sources may already own fixtures. Preserve their IDs, data and operational state.
    pass
