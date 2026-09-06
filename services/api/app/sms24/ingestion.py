"""Persistence and ingestion engine for normalized SMS24 provider data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sport import Sport
from app.models.sports_live import (
    SportsCompetition,
    SportsCompetitor,
    SportsDataSource,
    SportsFixture,
    SportsFixtureParticipant,
)
from app.sms24.providers import (
    ProviderCompetition,
    ProviderFetchResult,
    ProviderFixture,
    ProviderParticipant,
    SportsDataProvider,
)


ALLOWED_FIXTURE_STATUSES = {
    "scheduled",
    "live",
    "finished",
    "postponed",
    "cancelled",
    "suspended",
    "unknown",
}

ALLOWED_COMPETITOR_TYPES = {
    "team",
    "athlete",
    "pair",
    "selection",
    "other",
}


@dataclass(slots=True)
class SMS24IngestionStats:
    provider_slug: str
    fixtures_processed: int = 0
    competitions_processed: int = 0
    competitors_processed: int = 0
    participants_processed: int = 0
    fetched_at: datetime | None = None


class SMS24IngestionRepository:
    """PostgreSQL persistence boundary for SMS24 ingestion."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_source(
        self,
        slug: str,
    ) -> SportsDataSource | None:
        stmt = select(SportsDataSource).where(
            SportsDataSource.slug == slug,
            SportsDataSource.is_active.is_(True),
        )
        return await self.session.scalar(stmt)

    async def get_active_sport(
        self,
        slug: str,
    ) -> Sport | None:
        stmt = select(Sport).where(
            Sport.slug == slug,
            Sport.is_active.is_(True),
        )
        return await self.session.scalar(stmt)

    async def upsert_competition(
        self,
        *,
        source_id,
        sport_id,
        competition: ProviderCompetition,
        fetched_at: datetime,
    ) -> SportsCompetition:
        stmt = (
            insert(SportsCompetition)
            .values(
                source_id=source_id,
                sport_id=sport_id,
                external_id=competition.external_id,
                name=competition.name,
                country_code=competition.country_code,
                season=competition.season,
                logo_url=competition.logo_url,
                source_updated_at=competition.source_updated_at,
                fetched_at=fetched_at,
            )
            .on_conflict_do_update(
                constraint="uq_sports_competitions_source_external",
                set_={
                    "sport_id": sport_id,
                    "name": competition.name,
                    "country_code": competition.country_code,
                    "season": competition.season,
                    "logo_url": competition.logo_url,
                    "source_updated_at": competition.source_updated_at,
                    "fetched_at": fetched_at,
                },
            )
            .returning(SportsCompetition)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def upsert_competitor(
        self,
        *,
        source_id,
        sport_id,
        participant: ProviderParticipant,
        fetched_at: datetime,
    ) -> SportsCompetitor:
        stmt = (
            insert(SportsCompetitor)
            .values(
                source_id=source_id,
                sport_id=sport_id,
                external_id=participant.external_id,
                competitor_type=participant.competitor_type,
                name=participant.name,
                short_name=participant.short_name,
                country_code=participant.country_code,
                logo_url=participant.logo_url,
                metadata_json=participant.metadata,
                fetched_at=fetched_at,
            )
            .on_conflict_do_update(
                constraint="uq_sports_competitors_source_external",
                set_={
                    "sport_id": sport_id,
                    "competitor_type": participant.competitor_type,
                    "name": participant.name,
                    "short_name": participant.short_name,
                    "country_code": participant.country_code,
                    "logo_url": participant.logo_url,
                    "metadata_json": participant.metadata,
                    "fetched_at": fetched_at,
                },
            )
            .returning(SportsCompetitor)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def upsert_fixture(
        self,
        *,
        source_id,
        sport_id,
        competition_id,
        fixture: ProviderFixture,
        fetched_at: datetime,
    ) -> SportsFixture:
        stmt = (
            insert(SportsFixture)
            .values(
                source_id=source_id,
                sport_id=sport_id,
                competition_id=competition_id,
                external_id=fixture.external_id,
                name=fixture.name,
                starts_at=fixture.starts_at,
                status=fixture.status,
                live_clock=fixture.live_clock,
                venue=fixture.venue,
                result_json=fixture.result,
                metadata_json=fixture.metadata,
                source_updated_at=fixture.source_updated_at,
                fetched_at=fetched_at,
            )
            .on_conflict_do_update(
                constraint="uq_sports_fixtures_source_external",
                set_={
                    "sport_id": sport_id,
                    "competition_id": competition_id,
                    "name": fixture.name,
                    "starts_at": fixture.starts_at,
                    "status": fixture.status,
                    "live_clock": fixture.live_clock,
                    "venue": fixture.venue,
                    "result_json": fixture.result,
                    "metadata_json": fixture.metadata,
                    "source_updated_at": fixture.source_updated_at,
                    "fetched_at": fetched_at,
                },
            )
            .returning(SportsFixture)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def upsert_participant(
        self,
        *,
        fixture_id,
        competitor_id,
        participant: ProviderParticipant,
    ) -> SportsFixtureParticipant:
        stmt = (
            insert(SportsFixtureParticipant)
            .values(
                fixture_id=fixture_id,
                competitor_id=competitor_id,
                position=participant.position,
                role=participant.role,
                score_json=participant.score,
                result_status=participant.result_status,
            )
            .on_conflict_do_update(
                constraint="uq_sports_fixture_participant",
                set_={
                    "position": participant.position,
                    "role": participant.role,
                    "score_json": participant.score,
                    "result_status": participant.result_status,
                },
            )
            .returning(SportsFixtureParticipant)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def mark_source_success(
        self,
        source: SportsDataSource,
        *,
        checked_at: datetime,
    ) -> None:
        source.health_status = "healthy"
        source.last_success_at = checked_at
        source.last_checked_at = checked_at

    async def mark_source_failure(
        self,
        source: SportsDataSource,
        *,
        checked_at: datetime,
    ) -> None:
        source.health_status = "degraded"
        source.last_failure_at = checked_at
        source.last_checked_at = checked_at

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class SMS24IngestionService:
    """Normalize provider results into SMS24 canonical storage."""

    def __init__(
        self,
        repository: SMS24IngestionRepository,
    ) -> None:
        self.repository = repository

    async def ingest_provider_result(
        self,
        *,
        provider: SportsDataProvider,
        result: ProviderFetchResult,
    ) -> SMS24IngestionStats:
        provider_slug = provider.slug.strip().lower()

        source = await self.repository.get_active_source(
            provider_slug
        )
        if source is None:
            raise ValueError(
                f"Active SMS24 source not configured: {provider_slug}"
            )

        fetched_at = result.fetched_at or datetime.now(timezone.utc)

        stats = SMS24IngestionStats(
            provider_slug=provider_slug,
            fetched_at=fetched_at,
        )

        try:
            for fixture in result.fixtures:
                await self._ingest_fixture(
                    source=source,
                    fixture=fixture,
                    fetched_at=fetched_at,
                    stats=stats,
                )

            await self.repository.mark_source_success(
                source,
                checked_at=fetched_at,
            )
            await self.repository.commit()

        except Exception:
            await self.repository.rollback()
            raise

        return stats

    async def _ingest_fixture(
        self,
        *,
        source: SportsDataSource,
        fixture: ProviderFixture,
        fetched_at: datetime,
        stats: SMS24IngestionStats,
    ) -> None:
        self._validate_fixture(fixture)

        sport = await self.repository.get_active_sport(
            fixture.sport_slug
        )
        if sport is None:
            raise ValueError(
                "Unknown or inactive sport for SMS24 ingestion: "
                f"{fixture.sport_slug}"
            )

        competition_id = None

        if fixture.competition is not None:
            competition = await self.repository.upsert_competition(
                source_id=source.id,
                sport_id=sport.id,
                competition=fixture.competition,
                fetched_at=fetched_at,
            )
            competition_id = competition.id
            stats.competitions_processed += 1

        stored_fixture = await self.repository.upsert_fixture(
            source_id=source.id,
            sport_id=sport.id,
            competition_id=competition_id,
            fixture=fixture,
            fetched_at=fetched_at,
        )

        stats.fixtures_processed += 1

        seen_external_ids: set[str] = set()

        for participant in fixture.participants:
            self._validate_participant(participant)

            if participant.external_id in seen_external_ids:
                continue

            seen_external_ids.add(participant.external_id)

            competitor = await self.repository.upsert_competitor(
                source_id=source.id,
                sport_id=sport.id,
                participant=participant,
                fetched_at=fetched_at,
            )

            stats.competitors_processed += 1

            await self.repository.upsert_participant(
                fixture_id=stored_fixture.id,
                competitor_id=competitor.id,
                participant=participant,
            )

            stats.participants_processed += 1

    @staticmethod
    def _validate_fixture(
        fixture: ProviderFixture,
    ) -> None:
        if not fixture.external_id.strip():
            raise ValueError(
                "Provider fixture external_id must not be empty"
            )

        if not fixture.sport_slug.strip():
            raise ValueError(
                "Provider fixture sport_slug must not be empty"
            )

        if fixture.status not in ALLOWED_FIXTURE_STATUSES:
            raise ValueError(
                f"Unsupported SMS24 fixture status: {fixture.status}"
            )

        if fixture.starts_at.tzinfo is None:
            raise ValueError(
                "SMS24 fixture starts_at must be timezone-aware"
            )

    @staticmethod
    def _validate_participant(
        participant: ProviderParticipant,
    ) -> None:
        if not participant.external_id.strip():
            raise ValueError(
                "Provider participant external_id must not be empty"
            )

        if not participant.name.strip():
            raise ValueError(
                "Provider participant name must not be empty"
            )

        if (
            participant.competitor_type
            not in ALLOWED_COMPETITOR_TYPES
        ):
            raise ValueError(
                "Unsupported SMS24 competitor type: "
                f"{participant.competitor_type}"
            )

        if participant.position < 0:
            raise ValueError(
                "SMS24 participant position must be non-negative"
            )
