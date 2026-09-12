"""Standings fallback orchestration with caller-owned transactions."""

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sports_live import SportsSeason
from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.registry import ProviderRegistry
from app.sms24.providers.standings import (
    ProviderStanding,
    ProviderStandingsRequest,
    ProviderStandingsResult,
    validate_standings_request,
)
from app.sms24.providers.standings_normalization import validate_standing
from app.sms24.runner import SMS24ProviderAttempt, SMS24RunnerRepository
from app.sms24.standings import StandingsIngestionResult, StandingsIngestionService


@dataclass(slots=True)
class StandingsRunnerResult:
    provider_slug: str
    ingestion: StandingsIngestionResult
    attempts: list[SMS24ProviderAttempt]


class StandingsAllProvidersFailed(RuntimeError):
    def __init__(self, attempts: list[SMS24ProviderAttempt]) -> None:
        self.attempts = attempts
        super().__init__("All configured SMS24 standings providers failed")


class StandingsProviderRunner:
    """API-Football first, Sportmonks second, using explicit provider season mappings.

    Empty valid results succeed, without deleting old standings or degrading health.
    Each ingestion attempt uses a savepoint; no outer commit or rollback is issued.
    Provider/validation failures fall back, but database errors propagate to the caller.
    """

    PROVIDER_PRIORITY = ("api-football", "sportmonks")

    def __init__(
        self,
        *,
        session: AsyncSession,
        registry: ProviderRegistry,
        ingestion_service: StandingsIngestionService,
        max_result_age: timedelta = timedelta(minutes=10),
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        if max_result_age < timedelta(0):
            raise ValueError("Standings max_result_age must be nonnegative")
        self.session = session
        self.registry = registry
        self.ingestion_service = ingestion_service
        self.repository = SMS24RunnerRepository(session)
        self.max_result_age = max_result_age
        self.now_fn = now_fn or (lambda: datetime.now(UTC))

    def _validate_result(self, result: ProviderStandingsResult) -> None:
        if not isinstance(result, ProviderStandingsResult) or not isinstance(result.rows, list):
            raise ValueError("Invalid standings result")
        timestamp = result.fetched_at
        if (
            not isinstance(timestamp, datetime)
            or timestamp.tzinfo is None
            or timestamp.utcoffset() is None
        ):
            raise ValueError("Invalid standings fetched_at")
        if self.now_fn() - timestamp > self.max_result_age:
            raise ValueError("Stale standings result")
        for row in result.rows:
            if not isinstance(row, ProviderStanding):
                raise ValueError("Invalid standings row")
            validate_standing(row)

    async def run(
        self,
        *,
        season_id: uuid.UUID,
        targets: Mapping[str, ProviderStandingsRequest],
    ) -> StandingsRunnerResult:
        if not targets or set(targets) - set(self.PROVIDER_PRIORITY):
            raise ValueError("Supply supported standings provider mappings")
        for slug, target in targets.items():
            validate_standings_request(target)
            if slug == "api-football" and target.league_external_id is None:
                raise ValueError("API-Football standings require a league mapping")
        if await self.session.get(SportsSeason, season_id) is None:
            raise ValueError("Standings require an existing canonical season")
        attempts = []
        for slug in self.PROVIDER_PRIORITY:
            target = targets.get(slug)
            if target is None:
                continue
            source = await self.repository.get_active_source(slug)
            if source is None:
                attempts.append(SMS24ProviderAttempt(slug, False, "source_not_active"))
                continue
            source_id = source.id
            try:
                provider = self.registry.get(slug)
                fetch = getattr(provider, "fetch_standings", None)
                if not callable(fetch):
                    raise KeyError(slug)
            except KeyError:
                await self.repository.mark_unavailable(slug, checked_at=self.now_fn())
                attempts.append(SMS24ProviderAttempt(slug, False, "provider_not_registered"))
                continue
            try:
                health = await provider.check_health()
                healthy = health.is_healthy
            except Exception:
                healthy = False
            if not healthy:
                await self.repository.mark_failure(slug, checked_at=self.now_fn())
                attempts.append(SMS24ProviderAttempt(slug, False, "health_check_failed"))
                continue
            try:
                result = await fetch(
                    season=target.season, league_external_id=target.league_external_id
                )
                self._validate_result(result)
            except ProviderAccessRestrictedError:
                attempts.append(SMS24ProviderAttempt(slug, False, "provider_access_restricted"))
                continue
            except Exception:
                # Do not expose upstream exceptions, response bodies, URLs or credentials.
                await self.repository.mark_failure(slug, checked_at=self.now_fn())
                attempts.append(SMS24ProviderAttempt(slug, False, "fetch_or_payload_failed"))
                continue
            try:
                async with self.session.begin_nested():
                    ingestion = await self.ingestion_service.ingest_provider_result(
                        source_id=source_id,
                        season_id=season_id,
                        result=result,
                    )
                    checked_at = self.now_fn()
                    source.health_status = "healthy"
                    source.last_success_at = checked_at
                    source.last_checked_at = checked_at
                    await self.session.flush()
            except ValueError:
                await self.repository.mark_failure(slug, checked_at=self.now_fn())
                attempts.append(SMS24ProviderAttempt(slug, False, "ingestion_validation_failed"))
                continue
            attempts.append(SMS24ProviderAttempt(slug, True))
            return StandingsRunnerResult(slug, ingestion, attempts)
        raise StandingsAllProvidersFailed(attempts)
