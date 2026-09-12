"""Add SMS24 News observations and explicit multisport associations.

Revision ID: 20260912_0031
Revises: 20260911_0030
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260912_0031"
down_revision = "20260911_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sports_news_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(160), nullable=True),
        sa.Column("observation_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("excerpt", sa.String(1000), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("publisher_name", sa.String(240), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language_code", sa.String(40), nullable=True),
        sa.Column("image_url", sa.String(2048), nullable=True),
        sa.Column("image_credit", sa.String(500), nullable=True),
        sa.Column("news_type", sa.String(80), nullable=True),
        sa.Column("source_category", sa.String(200), nullable=True),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publication_status", sa.String(20), server_default="pending", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["sports_data_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "source_id", "observation_key", name="uq_sports_news_articles_observation"
        ),
        sa.CheckConstraint(
            "publication_status IN ('pending', 'published', 'withheld')",
            name="ck_sports_news_articles_publication_status",
        ),
    )
    for column in ("source_id", "published_at", "fetched_at", "publication_status"):
        op.create_index(f"ix_sports_news_articles_{column}", "sports_news_articles", [column])
    for table, column, target in (
        ("sports_news_article_sports", "sport_id", "sports"),
        (
            "sports_news_article_competitions",
            "canonical_competition_id",
            "sports_canonical_competitions",
        ),
        (
            "sports_news_article_competitors",
            "canonical_competitor_id",
            "sports_canonical_competitors",
        ),
        ("sports_news_article_countries", "country_id", "countries"),
    ):
        op.create_table(
            table,
            sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(column, postgresql.UUID(as_uuid=True), nullable=False),
            sa.PrimaryKeyConstraint("article_id", column),
            sa.ForeignKeyConstraint(
                ["article_id"], ["sports_news_articles.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint([column], [f"{target}.id"], ondelete="RESTRICT"),
        )
        op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    for table in (
        "sports_news_article_countries",
        "sports_news_article_competitors",
        "sports_news_article_competitions",
        "sports_news_article_sports",
    ):
        op.drop_table(table)
    op.drop_table("sports_news_articles")
