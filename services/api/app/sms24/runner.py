"""Resilient multi-provider runner for SMS24 / Live."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sports_live import SportsDataSource
from app.sms24.ingestion import (
    SMS24IngestionService,
    SMS24IngestionStats,
)
from app.sms24.providers import (
    ProviderFetchResult,
    ProviderRegistry,
)


@dataclass(frozen=True, slots=True)
class SMS24SourceRef:
    """Detached provider source identity used by the runner."""

    slug: str


@dataclass(slots=True)
class SMS24ProviderAttempt:
    provider_slug: str
    success: bool
    reason: str | None = None


@dataclass(slots=True)
class SMS24RunnerResult:
    provider_slug: str
    ingestion: SMS24IngestionStats
    attempts: list[SMS24ProviderAttempt] = field(
        default_factory=list
    )


class SMS24AllProvidersFailed(RuntimeError):
    """Raised when every configured SMS24 provider failed."""


class SMS24RunnerRepository:
    """Persistence needed by the provider orchestration layer."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active_sources(
        self,
    ) -> list[SMS24SourceRef]:
        stmt = (
            select(SportsDataSource.slug)
            .where(SportsDataSource.is_active.is_(True))
            .order_by(
                SportsDataSource.priority.asc(),
                SportsDataSource.slug.asc(),
            )
        )

        result = await self.session.execute(stmt)
        return [
            SMS24SourceRef(slug=slug)
            for slug in result.scalars().all()
        ]

    async def get_active_source(
        self,
        slug: str,
    ) -> SportsDataSource | None:
        stmt = select(SportsDataSource).where(
            SportsDataSource.slug == slug,
            SportsDataSource.is_active.is_(True),
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_failure(
        self,
        slug: str,
        *,
        checked_at: datetime,
    ) -> None:
        source = await self.get_active_source(slug)

        if source is None:
            return

        source.health_status = "degraded"
        source.last_failure_at = checked_at
        source.last_checked_at = checked_at

    async def mark_unavailable(
        self,
        slug: str,
        *,
        checked_at: datetime,
    ) -> None:
        source = await self.get_active_source(slug)

        if source is None:
            return

        source.health_status = "unavailable"
        source.last_failure_at = checked_at
        source.last_checked_at = checked_at

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class SMS24ProviderRunner:
    """Try SMS24 providers in priority order with automatic fallback."""

    def __init__(
        self,
        *,
        registry: ProviderRegistry,
        repository: SMS24RunnerRepository,
        ingestion_service: SMS24IngestionService,
        max_result_age: timedelta = timedelta(minutes=10),
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.registry = registry
        self.repository = repository
        self.ingestion_service = ingestion_service
        self.max_result_age = max_result_age
        self.now_fn = now_fn or (
            lambda: datetime.now(timezone.utc)
        )

    async def run(
        self,
        *,
        sport_slug: str | None = None,
        starts_from: datetime | None = None,
        starts_until: datetime | None = None,
        live_only: bool = False,
    ) -> SMS24RunnerResult:
        sources = await self.repository.list_active_sources()

        if not sources:
            raise SMS24AllProvidersFailed(
                "No active SMS24 data source configured"
            )

        attempts: list[SMS24ProviderAttempt] = []

        for source in sources:
            slug = source.slug.strip().lower()

            try:
                provider = self.registry.get(slug)
            except KeyError:
                await self._record_unavailable(slug)
                attempts.append(
                    SMS24ProviderAttempt(
                        provider_slug=slug,
                        success=False,
                        reason="provider_not_registered",
                    )
                )
                continue

            try:
                health = await provider.check_health()
            except Exception:
                await self._record_failure(slug)
                attempts.append(
                    SMS24ProviderAttempt(
                        provider_slug=slug,
                        success=False,
                        reason="health_check_failed",
                    )
                )
                continue

            if not health.is_healthy:
                await self._record_failure(slug)
                attempts.append(
                    SMS24ProviderAttempt(
                        provider_slug=slug,
                        success=False,
                        reason="provider_unhealthy",
                    )
                )
                continue

            try:
                result = await provider.fetch_fixtures(
                    sport_slug=sport_slug,
                    starts_from=starts_from,
                    starts_until=starts_until,
                    live_only=live_only,
                )
            except Exception:
                await self._record_failure(slug)
                attempts.append(
                    SMS24ProviderAttempt(
                        provider_slug=slug,
                        success=False,
                        reason="fetch_failed",
                    )
                )
                continue

            freshness_error = self._freshness_error(result)

            if freshness_error is not None:
                await self._record_failure(slug)
                attempts.append(
                    SMS24ProviderAttempt(
                        provider_slug=slug,
                        success=False,
                        reason=freshness_error,
                    )
                )
                continue

            try:
                ingestion = (
                    await self.ingestion_service.ingest_provider_result(
                        provider=provider,
                        result=result,
                    )
                )
            except Exception:
                # Ingestion service has already rolled back its transaction.
                # Health state is therefore persisted afterwards.
                await self._record_failure(slug)
                attempts.append(
                    SMS24ProviderAttempt(
                        provider_slug=slug,
                        success=False,
                        reason="ingestion_failed",
                    )
                )
                continue

            attempts.append(
                SMS24ProviderAttempt(
                    provider_slug=slug,
                    success=True,
                )
            )

            return SMS24RunnerResult(
                provider_slug=slug,
                ingestion=ingestion,
                attempts=attempts,
            )

        details = ", ".join(
            f"{attempt.provider_slug}:{attempt.reason}"
            for attempt in attempts
        )

        raise SMS24AllProvidersFailed(
            f"All SMS24 providers failed ({details})"
        )

    def _freshness_error(
        self,
        result: ProviderFetchResult,
    ) -> str | None:
        if result.fetched_at is None:
            return None

        fetched_at = result.fetched_at

        if (
            fetched_at.tzinfo is None
            or fetched_at.utcoffset() is None
        ):
            return "invalid_freshness_timestamp"

        now = self.now_fn()

        if now - fetched_at > self.max_result_age:
            return "stale_provider_result"

        return None

    async def _record_failure(
        self,
        slug: str,
    ) -> None:
        checked_at = self.now_fn()

        try:
            await self.repository.rollback()
            await self.repository.mark_failure(
                slug,
                checked_at=checked_at,
            )
            await self.repository.commit()
        except Exception:
            await self.repository.rollback()
            raise

    async def _record_unavailable(
        self,
        slug: str,
    ) -> None:
        checked_at = self.now_fn()

        try:
            await self.repository.rollback()
            await self.repository.mark_unavailable(
                slug,
                checked_at=checked_at,
            )
            await self.repository.commit()
        except Exception:
            await self.repository.rollback()
            raise
