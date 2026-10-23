"""Add a non-destructive catalogue for SMS24 multisport discovery.

Revision ID: 20261023_0044
Revises: 20261017_0043
"""
import uuid

import sqlalchemy as sa
from alembic import op

revision = "20261023_0044"
down_revision = "20261017_0043"
branch_labels = None
depends_on = None

SPORTS = (
    ("rugby", "Rugby", "Rugby à XV, à XIII et à 7"),
    ("handball", "Handball", "Handball"),
    ("volleyball", "Volleyball", "Volleyball et beach-volley"),
    ("tennis", "Tennis", "Tennis simple et double"),
    ("hockey", "Hockey", "Hockey sur glace et sur gazon"),
    ("baseball", "Baseball", "Baseball"),
    ("american-football", "Football américain", "Football américain"),
    ("cricket", "Cricket", "Cricket"),
    ("swimming", "Natation", "Natation sportive"),
    ("cycling", "Cyclisme", "Cyclisme"),
    ("boxing", "Boxe", "Boxe"),
    ("wrestling", "Lutte", "Lutte"),
    ("judo", "Judo", "Judo"),
    ("taekwondo", "Taekwondo", "Taekwondo"),
    ("golf", "Golf", "Golf"),
    ("badminton", "Badminton", "Badminton"),
    ("table-tennis", "Tennis de table", "Tennis de table"),
    ("futsal", "Futsal", "Football en salle"),
)


def upgrade() -> None:
    statement = sa.text(
        "INSERT INTO sports (id, slug, name, description, is_active) "
        "VALUES (:id, :slug, :name, :description, true) "
        "ON CONFLICT (slug) DO NOTHING"
    )
    for slug, name, description in SPORTS:
        op.get_bind().execute(
            statement,
            {
                "id": uuid.uuid5(uuid.NAMESPACE_URL, f"sms24:sport:{slug}"),
                "slug": slug,
                "name": name,
                "description": description,
            },
        )


def downgrade() -> None:
    # Keep catalogue entries: athlete profiles or fixtures may reference them.
    pass
