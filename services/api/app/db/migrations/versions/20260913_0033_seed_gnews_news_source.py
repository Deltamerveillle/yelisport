"""Seed GNews as an SMS24 News source.

Revision ID: 20260913_0033
Revises: 20260912_0032
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20260913_0033"
down_revision = "20260912_0032"
branch_labels = None
depends_on = None


GNEWS_SOURCE_ID = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "sms24:source:gnews",
)

GNEWS_NEWS_CAPABILITY_ID = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "sms24:source-capability:gnews:news",
)


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            INSERT INTO sports_data_sources
                (
                    id,
                    slug,
                    name,
                    provider_type,
                    priority,
                    is_active,
                    health_status
                )
            VALUES
                (
                    :id,
                    'gnews',
                    'GNews',
                    'api',
                    30,
                    true,
                    'unavailable'
                )
            ON CONFLICT (slug) DO UPDATE
            SET
                name = EXCLUDED.name,
                provider_type = EXCLUDED.provider_type,
                priority = EXCLUDED.priority
            """
        ),
        {"id": GNEWS_SOURCE_ID},
    )

    source_id = bind.execute(
        sa.text(
            """
            SELECT id
            FROM sports_data_sources
            WHERE slug = 'gnews'
            """
        )
    ).scalar_one()

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
                    'news',
                    30,
                    true
                )
            ON CONFLICT (source_id, capability) DO UPDATE
            SET
                priority = EXCLUDED.priority,
                is_active = true
            """
        ),
        {
            "id": GNEWS_NEWS_CAPABILITY_ID,
            "source_id": source_id,
        },
    )


def downgrade() -> None:
    # Match the upgrade conflict key: an existing capability may have another UUID.
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            DELETE FROM sports_data_source_capabilities
            WHERE source_id IN (
                SELECT id FROM sports_data_sources WHERE slug = 'gnews'
            )
            AND capability = 'news'
            """
        ),
    )

    # Preserve the GNews source itself. It may already own News articles,
    # and deleting it could cascade or invalidate operational data.
