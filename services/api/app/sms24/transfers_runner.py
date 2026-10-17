"""Aggregate explicit Transfers targets without resolving identities or writing health.

The caller owns the outer transaction. Each provider batch gets a savepoint;
validation failures are local attempts, while unexpected database errors propagate.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.sms24.providers.base import ProviderHealthResult
from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.registry import ProviderRegistry
from app.sms24.providers.transfers import (
    ProviderTransfer,
    ProviderTransfersResult,
    _text,
    _timestamp,
    validate_transfer,
)
from app.sms24.runner import SMS24RunnerRepository
from app.sms24.transfers import SMS24TransfersRepository


@dataclass(slots=True)
class TransfersProviderAttempt:
    provider_slug: str
    success: bool
    reason: str | None = None
    observations_processed: int = 0


@dataclass(slots=True)
class TransfersRunnerResult:
    attempts: list[TransfersProviderAttempt]

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


class TransfersAllProvidersFailed(RuntimeError):
    def __init__(self, attempts: list[TransfersProviderAttempt]) -> None:
        self.attempts = attempts
        super().__init__("No targeted SMS24 Transfers provider succeeded")


class TransfersRunner:
    def __init__(self, *, session: AsyncSession, registry: ProviderRegistry) -> None:
        self.session = session
        self.registry = registry
        self.repository = SMS24RunnerRepository(session)
        self.ingestion_repository = SMS24TransfersRepository(session)

    @staticmethod
    def _validate_result(result: ProviderTransfersResult, athlete_external_id: str) -> None:
        if not isinstance(result, ProviderTransfersResult):
            raise ValueError("Invalid Transfers result")
        _timestamp(result.fetched_at, required=True)
        if not isinstance(result.transfers, tuple | list):
            raise ValueError("Invalid Transfers observations")
        for transfer in result.transfers:
            if not isinstance(transfer, ProviderTransfer):
                raise ValueError("Invalid Transfers observation")
            validate_transfer(transfer)
            if transfer.athlete_external_id != athlete_external_id:
                raise ValueError("Transfers athlete does not match target")

    async def run(self, *, targets: Mapping[str, str]) -> TransfersRunnerResult:
        if not isinstance(targets, Mapping) or not targets:
            raise ValueError("Supply explicit Transfers targets")
        for slug, athlete_id in targets.items():
            if not isinstance(slug, str) or not slug or slug != slug.strip().lower():
                raise ValueError("Transfers source slugs must be normalized")
            _text(athlete_id, 160, required=True)

        slugs = await self.repository.list_active_sources_for_capability("transfers")
        attempts = [
            TransfersProviderAttempt(slug, False, "transfers_capability_not_active")
            for slug in sorted(set(targets) - set(slugs))
        ]
        for slug in slugs:
            if slug not in targets:
                continue
            source = await self.repository.get_active_source_for_capability(slug, "transfers")
            if source is None:
                attempts.append(
                    TransfersProviderAttempt(slug, False, "transfers_capability_not_active")
                )
                continue
            source_id = source.id
            try:
                provider = self.registry.get(slug)
            except KeyError:
                attempts.append(TransfersProviderAttempt(slug, False, "provider_not_registered"))
                continue
            fetch = getattr(provider, "fetch_transfers", None)
            if not callable(fetch):
                attempts.append(TransfersProviderAttempt(slug, False, "transfers_not_supported"))
                continue
            try:
                health = await provider.check_health()
                if not isinstance(health, ProviderHealthResult) or health.is_healthy is not True:
                    raise ValueError("Invalid or unhealthy Transfers provider")
            except ProviderAccessRestrictedError:
                attempts.append(TransfersProviderAttempt(slug, False, "provider_access_restricted"))
                continue
            except SQLAlchemyError:
                raise
            except Exception:
                attempts.append(TransfersProviderAttempt(slug, False, "health_check_failed"))
                continue
            try:
                result = await fetch(athlete_external_id=targets[slug])
                self._validate_result(result, targets[slug])
            except ProviderAccessRestrictedError:
                attempts.append(TransfersProviderAttempt(slug, False, "provider_access_restricted"))
                continue
            except SQLAlchemyError:
                raise
            except Exception:
                attempts.append(TransfersProviderAttempt(slug, False, "fetch_or_payload_failed"))
                continue
            try:
                async with self.session.begin_nested():
                    for transfer in result.transfers:
                        await self.ingestion_repository.record_observation(
                            source_id=source_id, transfer=transfer, fetched_at=result.fetched_at
                        )
                    await self.session.flush()
            except ValueError:
                attempts.append(
                    TransfersProviderAttempt(slug, False, "ingestion_validation_failed")
                )
                continue
            attempts.append(
                TransfersProviderAttempt(slug, True, observations_processed=len(result.transfers))
            )
        if not any(attempt.success for attempt in attempts):
            raise TransfersAllProvidersFailed(attempts)
        return TransfersRunnerResult(attempts)
