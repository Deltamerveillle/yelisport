"""Complete SMS24 sports catalogue with football and basketball."""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20261104_0045"
down_revision = "20261023_0044"
branch_labels = None
depends_on = None

SPORTS = (
    ("football", "Football", "Football association"),
    ("basketball", "Basketball", "Basketball"),
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
    # Preserve existing sports and their references.
    pass
