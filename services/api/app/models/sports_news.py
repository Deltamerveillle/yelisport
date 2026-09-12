"""SMS24 News observations and explicit canonical links, without article clustering."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SportsNewsArticle(Base):
    __tablename__ = "sports_news_articles"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "observation_key", name="uq_sports_news_articles_observation"
        ),
        CheckConstraint(
            "publication_status IN ('pending', 'published', 'withheld')",
            name="ck_sports_news_articles_publication_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_data_sources.id", ondelete="RESTRICT"),
        index=True,
    )
    external_id: Mapped[str | None] = mapped_column(String(160))
    observation_key: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(500))
    excerpt: Mapped[str | None] = mapped_column(String(1000))
    source_url: Mapped[str] = mapped_column(String(2048))
    publisher_name: Mapped[str | None] = mapped_column(String(240))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    language_code: Mapped[str | None] = mapped_column(String(40))
    image_url: Mapped[str | None] = mapped_column(String(2048))
    image_credit: Mapped[str | None] = mapped_column(String(500))
    news_type: Mapped[str | None] = mapped_column(String(80))
    source_category: Mapped[str | None] = mapped_column(String(200))
    provider_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # pending: retained, not approved for publication; published: explicitly publishable;
    # withheld: explicitly excluded. No automatic editorial promotion.
    publication_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class SportsNewsArticleSport(Base):
    __tablename__ = "sports_news_article_sports"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_news_articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )


class SportsNewsArticleCompetition(Base):
    __tablename__ = "sports_news_article_competitions"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_news_articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    canonical_competition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_canonical_competitions.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )


class SportsNewsArticleCompetitor(Base):
    __tablename__ = "sports_news_article_competitors"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_news_articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    canonical_competitor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_canonical_competitors.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )


class SportsNewsArticleCountry(Base):
    __tablename__ = "sports_news_article_countries"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports_news_articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    country_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("countries.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
