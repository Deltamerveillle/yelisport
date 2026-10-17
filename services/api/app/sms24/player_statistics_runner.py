"""Aggregate explicit Player Statistics targets without resolving identities or writing health.

The caller owns the outer transaction. Each provider batch gets a savepoint;
validation failures are local attempts, while unexpected database errors propagate.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sport import Sport
from app.sms24.player_statistics import SMS24PlayerStatisticsRepository
from app.sms24.providers.base import ProviderHealthResult
from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.player_statistics import (
    ProviderPlayerStatisticsResult,
    _text,
    validate_player_statistics_result,
)
from app.sms24.providers.registry import ProviderRegistry
from app.sms24.runner import SMS24RunnerRepository


@dataclass(frozen=True, slots=True)
class PlayerStatisticsTarget:
    athlete_external_id: str
    sport_id: uuid.UUID


@dataclass(slots=True)
class PlayerStatisticsProviderAttempt:
    provider_slug: str
    success: bool
    reason: str | None = None
    observations_processed: int = 0


@dataclass(slots=True)
class PlayerStatisticsRunnerResult:
    attempts: list[PlayerStatisticsProviderAttempt]

    @property
    def successes(self) -> int:
        return sum(attempt.success for attempt in self.attempts)

    @property
    def failures(self) -> int:
        return len(self.attempts) - self.successes

    @property
    def observations_processed(self) -> int:
        # Includes idempotent replays and stale snapshots ignored by the repository.
        return sum(attempt.observations_processed for attempt in self.attempts)


class PlayerStatisticsAllProvidersFailed(RuntimeError):
    def __init__(self, attempts: list[PlayerStatisticsProviderAttempt]) -> None:
        self.attempts = attempts
        super().__init__("No targeted SMS24 Player Statistics provider succeeded")


class PlayerStatisticsRunner:
    def __init__(self, *, session: AsyncSession, registry: ProviderRegistry) -> None:
        self.session = session
        self.registry = registry
        self.repository = SMS24RunnerRepository(session)
        self.ingestion_repository = SMS24PlayerStatisticsRepository(session)

    @staticmethod
    def _validate_result(result: ProviderPlayerStatisticsResult, athlete_external_id: str) -> None:
        # The frozen contract requires a tuple and validates each observation and timestamp.
        validate_player_statistics_result(result)
        for statistic in result.statistics:
            if statistic.athlete_external_id != athlete_external_id:
                raise ValueError("Player Statistics athlete does not match target")

    async def run(
        self,
        *,
        targets: Mapping[str, PlayerStatisticsTarget],
    ) -> PlayerStatisticsRunnerResult:
        if not isinstance(targets, Mapping) or not targets:
            raise ValueError("Supply explicit Player Statistics targets")
        targets = dict(targets)
        for slug, target in targets.items():
            if not isinstance(slug, str) or not slug or slug != slug.strip().lower():
                raise ValueError("Player Statistics source slugs must be normalized")
            if type(target) is not PlayerStatisticsTarget:
                raise ValueError("An explicit PlayerStatisticsTarget is required")
            _text(target.athlete_external_id, 160, required=True)
            if not isinstance(target.sport_id, uuid.UUID):
                raise ValueError("Player Statistics sport_id must be a UUID")

        # Validate the entire request before provider calls or observation writes.
        sport_ids = {target.sport_id for target in targets.values()}
        active_ids = set(
            await self.session.scalars(
                select(Sport.id).where(Sport.id.in_(sport_ids), Sport.is_active.is_(True))
            )
        )
        if active_ids != sport_ids:
            raise ValueError("Player Statistics target sports must exist and be active")

        slugs = await self.repository.list_active_sources_for_capability("statistics")
        attempts = [
            PlayerStatisticsProviderAttempt(slug, False, "statistics_capability_not_active")
            for slug in sorted(set(targets) - set(slugs))
        ]
        for slug in slugs:
            if slug not in targets:
                continue
            source = await self.repository.get_active_source_for_capability(slug, "statistics")
            if source is None:
                attempts.append(
                    PlayerStatisticsProviderAttempt(slug, False, "statistics_capability_not_active")
                )
                continue
            source_id = source.id
            try:
                provider = self.registry.get(slug)
            except KeyError:
                attempts.append(
                    PlayerStatisticsProviderAttempt(slug, False, "provider_not_registered")
                )
                continue
            fetch = getattr(provider, "fetch_player_statistics", None)
            if not callable(fetch):
                attempts.append(
                    PlayerStatisticsProviderAttempt(slug, False, "statistics_not_supported")
                )
                continue
            try:
                health = await provider.check_health()
                if not isinstance(health, ProviderHealthResult) or health.is_healthy is not True:
                    raise ValueError("Invalid or unhealthy PlayerStatistics provider")
            except ProviderAccessRestrictedError:
                attempts.append(
                    PlayerStatisticsProviderAttempt(slug, False, "provider_access_restricted")
                )
                continue
            except SQLAlchemyError:
                raise
            except Exception:
                attempts.append(PlayerStatisticsProviderAttempt(slug, False, "health_check_failed"))
                continue
            try:
                result = await fetch(athlete_external_id=targets[slug].athlete_external_id)
                self._validate_result(result, targets[slug].athlete_external_id)
            except ProviderAccessRestrictedError:
                attempts.append(
                    PlayerStatisticsProviderAttempt(slug, False, "provider_access_restricted")
                )
                continue
            except SQLAlchemyError:
                raise
            except Exception:
                attempts.append(
                    PlayerStatisticsProviderAttempt(slug, False, "fetch_or_payload_failed")
                )
                continue
            try:
                async with self.session.begin_nested():
                    for statistic in result.statistics:
                        await self.ingestion_repository.record_observation(
                            source_id=source_id,
                            sport_id=targets[slug].sport_id,
                            statistic=statistic,
                            fetched_at=result.fetched_at,
                        )
                    await self.session.flush()
            except SQLAlchemyError:
                raise
            except ValueError:
                attempts.append(
                    PlayerStatisticsProviderAttempt(slug, False, "ingestion_validation_failed")
                )
                continue
            attempts.append(
                PlayerStatisticsProviderAttempt(
                    slug, True, observations_processed=len(result.statistics)
                )
            )
        if not any(attempt.success for attempt in attempts):
            raise PlayerStatisticsAllProvidersFailed(attempts)
        return PlayerStatisticsRunnerResult(attempts)
