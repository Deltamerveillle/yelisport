"""Aggregate all eligible News sources with caller-owned transactions.

Health checks are local execution gates only. No News outcome changes global
SportsDataSource health or its success/failure/check timestamps. Database failures
propagate rather than being attributed to a provider or hidden as success.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.sms24.news import NewsIngestionResult, SMS24NewsRepository
from app.sms24.providers.base import ProviderHealthResult
from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.news import ProviderNewsResult, validate_news_article, validate_timestamp
from app.sms24.providers.news_registry import NewsProviderRegistry
from app.sms24.runner import SMS24RunnerRepository


@dataclass(slots=True)
class NewsProviderAttempt:
    provider_slug: str
    success: bool
    reason: str | None = None
    ingestion: NewsIngestionResult | None = None


@dataclass(slots=True)
class NewsRunnerResult:
    attempts: list[NewsProviderAttempt]
    ingestion: NewsIngestionResult

    @property
    def successes(self) -> int:
        return sum(attempt.success for attempt in self.attempts)

    @property
    def failures(self) -> int:
        return len(self.attempts) - self.successes


class NewsAllProvidersFailed(RuntimeError):
    def __init__(self, attempts: list[NewsProviderAttempt]) -> None:
        self.attempts = attempts
        super().__init__("All eligible SMS24 News providers failed")


class NoActiveNewsSourcesError(NewsAllProvidersFailed):
    def __init__(self) -> None:
        super().__init__([])
        self.args = ("No active SMS24 News source configured",)


class NewsRunner:
    def __init__(
        self,
        *,
        session: AsyncSession,
        registry: NewsProviderRegistry,
        ingestion_repository: SMS24NewsRepository | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self.registry = registry
        self.repository = SMS24RunnerRepository(session)
        self.ingestion_repository = ingestion_repository or SMS24NewsRepository(session)
        self.now_fn = now_fn or (lambda: datetime.now(UTC))

    async def run(self) -> NewsRunnerResult:
        slugs = await self.repository.list_active_sources_for_capability("news")
        if not slugs:
            raise NoActiveNewsSourcesError()
        attempts = []
        total = NewsIngestionResult()
        for slug in slugs:
            source = await self.repository.get_active_source_for_capability(slug, "news")
            if source is None:
                attempts.append(NewsProviderAttempt(slug, False, "news_capability_not_active"))
                continue
            source_id = source.id
            try:
                provider = self.registry.get(slug)
            except KeyError:
                attempts.append(NewsProviderAttempt(slug, False, "provider_not_registered"))
                continue
            try:
                health = await provider.check_health()
                if not isinstance(health, ProviderHealthResult) or not health.is_healthy:
                    raise ValueError("Invalid or unhealthy News provider health result")
            except ProviderAccessRestrictedError:
                attempts.append(NewsProviderAttempt(slug, False, "provider_access_restricted"))
                continue
            except Exception:
                attempts.append(NewsProviderAttempt(slug, False, "health_check_failed"))
                continue
            try:
                result = await provider.fetch_news()
                if not isinstance(result, ProviderNewsResult):
                    raise ValueError("Invalid News provider result")
                validate_timestamp(result.fetched_at, required=True)
                if not isinstance(result.articles, tuple | list):
                    raise ValueError("Invalid News articles")
                for article in result.articles:
                    validate_news_article(article)
            except ProviderAccessRestrictedError:
                attempts.append(NewsProviderAttempt(slug, False, "provider_access_restricted"))
                continue
            except Exception:
                attempts.append(NewsProviderAttempt(slug, False, "fetch_or_payload_failed"))
                continue
            try:
                # Isolate this provider's ingestion without writing shared source health.
                async with self.session.begin_nested():
                    stats = await self.ingestion_repository.ingest(
                        source_id=source_id, result=result
                    )
                    await self.session.flush()
            except ValueError:
                attempts.append(NewsProviderAttempt(slug, False, "ingestion_validation_failed"))
                continue
            attempts.append(NewsProviderAttempt(slug, True, ingestion=stats))
            total.articles_processed += stats.articles_processed
            total.articles_upserted += stats.articles_upserted
        if not any(attempt.success for attempt in attempts):
            raise NewsAllProvidersFailed(attempts)
        return NewsRunnerResult(attempts, total)
