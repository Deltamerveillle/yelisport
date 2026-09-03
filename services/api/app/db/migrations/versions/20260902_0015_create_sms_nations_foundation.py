"""Create SMS Nations country and eligibility foundation.

Revision ID: 20260902_0015
Revises: 20260902_0014
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260902_0015"
down_revision = "20260902_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "countries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("iso2", sa.String(length=2), nullable=False),
        sa.Column("iso3", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "continent_code",
            sa.String(length=2),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("iso2"),
        sa.UniqueConstraint("iso3"),
    )

    op.create_index(
        op.f("ix_countries_iso2"),
        "countries",
        ["iso2"],
        unique=True,
    )
    op.create_index(
        op.f("ix_countries_iso3"),
        "countries",
        ["iso3"],
        unique=True,
    )
    op.create_index(
        op.f("ix_countries_name"),
        "countries",
        ["name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_countries_continent_code"),
        "countries",
        ["continent_code"],
        unique=False,
    )

    op.add_column(
        "athletes",
        sa.Column(
            "residence_country_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_athletes_residence_country_id_countries",
        "athletes",
        "countries",
        ["residence_country_id"],
        ["id"],
    )

    op.create_index(
        op.f("ix_athletes_residence_country_id"),
        "athletes",
        ["residence_country_id"],
        unique=False,
    )

    op.create_table(
        "athlete_country_eligibilities",
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
            "country_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="declared",
            nullable=False,
        ),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "declared_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "documented_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "verified_at",
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
            "status IN ('declared', 'documented', 'verified')",
            name="ck_athlete_country_eligibilities_status",
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["country_id"],
            ["countries.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "athlete_id",
            "country_id",
            name="uq_athlete_country_eligibilities_athlete_country",
        ),
    )

    op.create_index(
        op.f("ix_athlete_country_eligibilities_athlete_id"),
        "athlete_country_eligibilities",
        ["athlete_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_athlete_country_eligibilities_country_id"),
        "athlete_country_eligibilities",
        ["country_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_athlete_country_eligibilities_status"),
        "athlete_country_eligibilities",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_athlete_country_eligibilities_status"),
        table_name="athlete_country_eligibilities",
    )
    op.drop_index(
        op.f("ix_athlete_country_eligibilities_country_id"),
        table_name="athlete_country_eligibilities",
    )
    op.drop_index(
        op.f("ix_athlete_country_eligibilities_athlete_id"),
        table_name="athlete_country_eligibilities",
    )
    op.drop_table("athlete_country_eligibilities")

    op.drop_index(
        op.f("ix_athletes_residence_country_id"),
        table_name="athletes",
    )
    op.drop_constraint(
        "fk_athletes_residence_country_id_countries",
        "athletes",
        type_="foreignkey",
    )
    op.drop_column("athletes", "residence_country_id")

    op.drop_index(
        op.f("ix_countries_continent_code"),
        table_name="countries",
    )
    op.drop_index(
        op.f("ix_countries_name"),
        table_name="countries",
    )
    op.drop_index(
        op.f("ix_countries_iso3"),
        table_name="countries",
    )
    op.drop_index(
        op.f("ix_countries_iso2"),
        table_name="countries",
    )
    op.drop_table("countries")
