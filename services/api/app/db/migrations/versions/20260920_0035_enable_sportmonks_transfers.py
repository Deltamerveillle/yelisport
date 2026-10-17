"""Enable Transfers only for the existing Sportmonks source.

Revision ID: 20260920_0035
Revises: 20260916_0034

An absent source is an explicit no-op, following 0032's existing-source-only seed.
Downgrade follows 0033: remove the logical capability even if it predated upgrade;
prior activation/priority state is not restored. Never create or modify a source.
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20260920_0035"
down_revision = "20260916_0034"
branch_labels = None
depends_on = None

SPORTMONKS_TRANSFERS_CAPABILITY_ID = uuid.uuid5(
    uuid.NAMESPACE_URL, "sms24:source-capability:sportmonks:transfers"
)


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO sports_data_source_capabilities
                (id, source_id, capability, priority, is_active)
            SELECT :id, id, 'transfers', priority, true
            FROM sports_data_sources
            WHERE slug = 'sportmonks'
            ON CONFLICT (source_id, capability) DO UPDATE
            SET priority = EXCLUDED.priority, is_active = true
            """
        ),
        {"id": SPORTMONKS_TRANSFERS_CAPABILITY_ID},
    )


def downgrade() -> None:
    # A pre-existing logical capability can have an unrelated UUID; remove it too.
    op.get_bind().execute(
        sa.text(
            """
            DELETE FROM sports_data_source_capabilities
            WHERE source_id IN (
                SELECT id FROM sports_data_sources WHERE slug = 'sportmonks'
            )
            AND capability = 'transfers'
            """
        )
    )
