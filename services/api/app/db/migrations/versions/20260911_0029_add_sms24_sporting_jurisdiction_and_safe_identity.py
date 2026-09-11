"""Add sporting jurisdiction and conservative canonical entity scopes.

Revision ID: 20260911_0029
Revises: 20260910_0028
"""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0029"
down_revision = "20260910_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("sports_competitions", "sports_canonical_competitions"):
        op.add_column(table, sa.Column("jurisdiction_name", sa.String(200), nullable=True))
        op.add_column(table, sa.Column("normalized_jurisdiction", sa.String(600), nullable=True))
    for table in ("sports_canonical_competitions", "sports_canonical_competitors"):
        op.add_column(
            table,
            sa.Column(
                "identity_scope",
                sa.String(24),
                nullable=False,
                server_default="provider_scoped",
            ),
        )
        op.create_check_constraint(
            f"ck_{table}_identity_scope",
            table,
            "identity_scope IN ('verified_context', 'provider_scoped')",
        )
    op.drop_index(
        "ix_sports_canonical_competitions_lookup", table_name="sports_canonical_competitions"
    )
    op.create_index(
        "ix_sports_canonical_competitions_lookup",
        "sports_canonical_competitions",
        ["sport_id", "normalized_name", "normalized_jurisdiction"],
    )
    # Legacy keys are never reused by the new scoped key format. Retain canonical
    # rows and their seasons as historical data, but do not endorse potentially
    # false legacy links. No observations or fixture identities are deleted.
    op.execute(
        "UPDATE sports_competitions SET canonical_competition_id = NULL "
        "WHERE canonical_competition_id IS NOT NULL"
    )
    op.execute(
        "UPDATE sports_competitors SET canonical_competitor_id = NULL "
        "WHERE canonical_competitor_id IS NOT NULL"
    )


def downgrade() -> None:
    # Invalidated legacy associations cannot safely be reconstructed automatically.
    op.drop_index(
        "ix_sports_canonical_competitions_lookup", table_name="sports_canonical_competitions"
    )
    op.create_index(
        "ix_sports_canonical_competitions_lookup",
        "sports_canonical_competitions",
        ["sport_id", "normalized_name", "country_code"],
    )
    for table in ("sports_canonical_competitors", "sports_canonical_competitions"):
        op.drop_constraint(f"ck_{table}_identity_scope", table, type_="check")
        op.drop_column(table, "identity_scope")
    for table in ("sports_canonical_competitions", "sports_competitions"):
        op.drop_column(table, "normalized_jurisdiction")
        op.drop_column(table, "jurisdiction_name")
