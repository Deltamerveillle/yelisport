"""Local News ingestion, with caller-owned transactions and no provider execution.

Updates replace editorial scalar fields (including explicit/default None values).
Associations are additive: omitted/empty lists NEVER remove existing links. Sports
coherence is checked against their union. No fuzzy resolution or intersource merge.

CAPABILITY BOUNDARY: before enabling any real News source, provider selection must
be separated by capability. The existing fixtures runner can select all active
SportsDataSource rows. This module seeds no sources and changes no runner/health.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sports_live import SportsCanonicalCompetition, SportsCanonicalCompetitor
from app.models.sports_news import (
    SportsNewsArticle,
    SportsNewsArticleCompetition,
    SportsNewsArticleCompetitor,
    SportsNewsArticleCountry,
    SportsNewsArticleSport,
)
from app.sms24.providers.news import (
    TEXT_LIMITS,
    ProviderNewsResult,
    build_news_observation_key,
    validate_news_article,
    validate_timestamp,
)


@dataclass(slots=True)
class NewsIngestionResult:
    articles_processed: int = 0
    articles_upserted: int = 0


class SMS24NewsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ingest(
        self, *, source_id: uuid.UUID, result: ProviderNewsResult
    ) -> NewsIngestionResult:
        """Atomically ingest this batch in a savepoint; never commit the outer transaction.

        Database errors propagate. Older fetched snapshots are ignored, including their
        associations. Equal timestamps may update. Stable identity is required.
        """
        if not isinstance(result, ProviderNewsResult) or not isinstance(source_id, uuid.UUID):
            raise ValueError("News requires a source UUID and normalized result")
        validate_timestamp(result.fetched_at, required=True)
        for article in result.articles:
            validate_news_article(article)
        stats = NewsIngestionResult()
        async with self.session.begin_nested():
            for article in result.articles:
                values = {name: getattr(article, name) for name in TEXT_LIMITS}
                values.update(
                    source_url=article.source_url,
                    image_url=article.image_url,
                    published_at=article.published_at,
                    provider_updated_at=article.provider_updated_at,
                    fetched_at=result.fetched_at,
                    publication_status=article.publication_status,
                )
                # ON CONFLICT also locks the observation until the caller's transaction ends.
                stmt = (
                    insert(SportsNewsArticle)
                    .values(
                        source_id=source_id,
                        observation_key=build_news_observation_key(
                            article.external_id, article.source_url
                        ),
                        **values,
                    )
                    .on_conflict_do_update(
                        constraint="uq_sports_news_articles_observation",
                        set_={**values, "updated_at": func.now()},
                        where=SportsNewsArticle.fetched_at <= result.fetched_at,
                    )
                    .returning(SportsNewsArticle.id)
                )
                article_id = (await self.session.execute(stmt)).scalar_one_or_none()
                stats.articles_processed += 1
                if article_id is None:
                    continue
                existing_sports = set(
                    await self.session.scalars(
                        select(SportsNewsArticleSport.sport_id).where(
                            SportsNewsArticleSport.article_id == article_id
                        )
                    )
                )
                sports = existing_sports | set(article.sport_ids)
                if article.publication_status == "published" and not sports:
                    raise ValueError("Published News requires at least one explicit sport")
                # Lock linked identities while checking coherence. Names are never inspected.
                for model, ids in (
                    (SportsCanonicalCompetition, article.canonical_competition_ids),
                    (SportsCanonicalCompetitor, article.canonical_competitor_ids),
                ):
                    rows = await self.session.execute(
                        select(model.id, model.sport_id).where(model.id.in_(ids)).with_for_update()
                    )
                    if any(sport_id not in sports for _, sport_id in rows):
                        raise ValueError("News canonical link has an incompatible sport")
                for link_model, column, ids in (
                    (SportsNewsArticleSport, "sport_id", article.sport_ids),
                    (
                        SportsNewsArticleCompetition,
                        "canonical_competition_id",
                        article.canonical_competition_ids,
                    ),
                    (
                        SportsNewsArticleCompetitor,
                        "canonical_competitor_id",
                        article.canonical_competitor_ids,
                    ),
                    (SportsNewsArticleCountry, "country_id", article.country_ids),
                ):
                    for identity in sorted(set(ids)):
                        await self.session.execute(
                            insert(link_model)
                            .values(article_id=article_id, **{column: identity})
                            .on_conflict_do_nothing(index_elements=["article_id", column])
                        )
                stats.articles_upserted += 1
        return stats
