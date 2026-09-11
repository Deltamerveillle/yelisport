"""Persistence and ingestion engine for normalized SMS24 provider data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sport import Sport
from app.models.sports_live import (
    SportsCanonicalCompetition,
    SportsCanonicalCompetitor,
    SportsCanonicalFixture,
    SportsCompetition,
    SportsCompetitor,
    SportsDataSource,
    SportsFixture,
    SportsFixtureParticipant,
    SportsSeason,
)
from app.sms24.canonical import (
    CanonicalFixtureCandidate,
    build_canonical_fixture_key,
    build_participant_signature,
)
from app.sms24.canonical_entities import (
    build_canonical_competition_key,
    build_canonical_competitor_key,
    normalize_identity_text,
    normalize_jurisdiction,
    normalize_season_label,
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
        canonical = await self.resolve_canonical_competition(
            sport_id=sport_id,
            source_id=source_id,
            competition=competition,
        )
        if competition.season:
            await self.resolve_season(
                canonical_competition_id=canonical.id,
                label=competition.season,
            )
        stmt = (
            insert(SportsCompetition)
            .values(
                source_id=source_id,
                sport_id=sport_id,
                canonical_competition_id=canonical.id,
                external_id=competition.external_id,
                name=competition.name,
                country_code=competition.country_code,
                jurisdiction_name=competition.jurisdiction_name,
                normalized_jurisdiction=normalize_jurisdiction(competition.jurisdiction_name) or None,
                season=competition.season,
                logo_url=competition.logo_url,
                source_updated_at=competition.source_updated_at,
                fetched_at=fetched_at,
            )
            .on_conflict_do_update(
                constraint="uq_sports_competitions_source_external",
                set_={
                    "sport_id": sport_id,
                    "canonical_competition_id": canonical.id,
                    "name": competition.name,
                    "country_code": competition.country_code,
                    "jurisdiction_name": competition.jurisdiction_name,
                    "normalized_jurisdiction": normalize_jurisdiction(competition.jurisdiction_name) or None,
                    "season": competition.season,
                    "logo_url": competition.logo_url,
                    "source_updated_at": competition.source_updated_at,
                    "fetched_at": fetched_at,
                },
            )
            .returning(SportsCompetition)
            .execution_options(populate_existing=True)
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
        canonical = await self.resolve_canonical_competitor(
            sport_id=sport_id,
            source_id=source_id,
            participant=participant,
        )
        stmt = (
            insert(SportsCompetitor)
            .values(
                source_id=source_id,
                sport_id=sport_id,
                canonical_competitor_id=canonical.id,
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
                    "canonical_competitor_id": canonical.id,
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
            .execution_options(populate_existing=True)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one()


    async def _resolve_exact(self, model, *, constraint, values, predicates):
        """Insert once, or read the winner of a concurrent unique-key insert."""
        exact_stmt = select(model).where(*predicates)
        existing = await self.session.scalar(exact_stmt)
        if existing is not None:
            return existing
        stmt = (
            insert(model)
            .values(**values)
            .on_conflict_do_nothing(constraint=constraint)
            .returning(model)
        )
        created = (await self.session.execute(stmt)).scalar_one_or_none()
        if created is not None:
            return created
        existing = await self.session.scalar(exact_stmt)
        if existing is None:
            raise RuntimeError(f"Unable to resolve SMS24 {model.__tablename__}")
        return existing

    async def resolve_canonical_competition(
        self, *, sport_id, source_id, competition: ProviderCompetition,
    ) -> SportsCanonicalCompetition:
        sport = await self.session.get(Sport, sport_id)
        if sport is None:
            raise ValueError("Unknown sport for SMS24 canonical competition")
        source = await self.session.get(SportsDataSource, source_id)
        if source is None:
            raise ValueError("Unknown source for SMS24 canonical competition")
        jurisdiction = normalize_jurisdiction(competition.jurisdiction_name)
        key = build_canonical_competition_key(
            sport.slug, competition.name, competition.jurisdiction_name,
            source_slug=source.slug, external_id=competition.external_id,
        )
        return await self._resolve_exact(
            SportsCanonicalCompetition,
            constraint="uq_sports_canonical_competitions_key",
            values={
                "sport_id": sport_id,
                "canonical_key": key,
                "identity_scope": "verified_context" if jurisdiction else "provider_scoped",
                "jurisdiction_name": competition.jurisdiction_name,
                "normalized_jurisdiction": jurisdiction or None,
                "name": competition.name,
                "normalized_name": normalize_identity_text(competition.name),
                "country_code": normalize_identity_text(competition.country_code) or None,
            },
            predicates=[SportsCanonicalCompetition.canonical_key == key],
        )

    async def resolve_canonical_competitor(
        self, *, sport_id, source_id, participant: ProviderParticipant,
    ) -> SportsCanonicalCompetitor:
        sport = await self.session.get(Sport, sport_id)
        if sport is None:
            raise ValueError("Unknown sport for SMS24 canonical competitor")
        source = await self.session.get(SportsDataSource, source_id)
        if source is None:
            raise ValueError("Unknown source for SMS24 canonical competitor")
        context = participant.country_code.strip() if participant.country_code else None
        if context and (len(context) != 2 or not context.isascii() or not context.isalpha()):
            context = None
        key = build_canonical_competitor_key(
            sport.slug, participant.competitor_type, participant.name, context,
            source_slug=source.slug, external_id=participant.external_id,
        )
        return await self._resolve_exact(
            SportsCanonicalCompetitor,
            constraint="uq_sports_canonical_competitors_key",
            values={
                "sport_id": sport_id,
                "canonical_key": key,
                "identity_scope": "verified_context" if context else "provider_scoped",
                "competitor_type": participant.competitor_type,
                "name": participant.name,
                "normalized_name": normalize_identity_text(participant.name),
                "country_code": normalize_identity_text(participant.country_code) or None,
            },
            predicates=[SportsCanonicalCompetitor.canonical_key == key],
        )

    async def resolve_season(self, *, canonical_competition_id, label: str) -> SportsSeason:
        normalized_label = normalize_season_label(label)
        return await self._resolve_exact(
            SportsSeason,
            constraint="uq_sports_seasons_competition_label",
            values={
                "canonical_competition_id": canonical_competition_id,
                "label": label,
                "normalized_label": normalized_label,
            },
            predicates=[
                SportsSeason.canonical_competition_id == canonical_competition_id,
                SportsSeason.normalized_label == normalized_label,
            ],
        )

    async def resolve_canonical_fixture(
        self,
        *,
        sport_id,
        candidate: CanonicalFixtureCandidate,
        tolerance_minutes: int = 5,
    ) -> SportsCanonicalFixture:
        """Resolve or create one provider-independent real-world fixture."""

        canonical_key = build_canonical_fixture_key(candidate)
        participant_signature = build_participant_signature(candidate)

        # Exact deterministic identity always wins.
        exact_stmt = select(SportsCanonicalFixture).where(
            SportsCanonicalFixture.canonical_key == canonical_key
        )
        exact = await self.session.scalar(exact_stmt)
        if exact is not None:
            return exact

        starts_from = candidate.starts_at - timedelta(
            minutes=tolerance_minutes
        )
        starts_until = candidate.starts_at + timedelta(
            minutes=tolerance_minutes
        )

        candidate_stmt = (
            select(SportsCanonicalFixture)
            .where(
                SportsCanonicalFixture.sport_id == sport_id,
                SportsCanonicalFixture.participant_signature
                == participant_signature,
                SportsCanonicalFixture.starts_at >= starts_from,
                SportsCanonicalFixture.starts_at <= starts_until,
            )
            .order_by(SportsCanonicalFixture.starts_at)
        )

        result = await self.session.execute(candidate_stmt)
        matches = list(result.scalars().all())

        # A single strong candidate inside the tolerance window is safe.
        if len(matches) == 1:
            return matches[0]

        # Zero candidates means a new event.
        # Multiple candidates are deliberately treated as ambiguous:
        # create a distinct canonical event rather than false-merge.
        create_stmt = (
            insert(SportsCanonicalFixture)
            .values(
                sport_id=sport_id,
                canonical_key=canonical_key,
                participant_signature=participant_signature,
                starts_at=candidate.starts_at,
            )
            .on_conflict_do_nothing(
                constraint="uq_sports_canonical_fixtures_key"
            )
            .returning(SportsCanonicalFixture)
        )

        created_result = await self.session.execute(create_stmt)
        created = created_result.scalar_one_or_none()

        if created is not None:
            return created

        # Concurrency safety: another transaction may have created
        # the deterministic identity between our SELECT and INSERT.
        concurrent = await self.session.scalar(exact_stmt)
        if concurrent is None:
            raise RuntimeError(
                "Unable to resolve SMS24 canonical fixture"
            )

        return concurrent

    async def upsert_fixture(
        self,
        *,
        source_id,
        sport_id,
        competition_id,
        canonical_fixture_id,
        fixture: ProviderFixture,
        fetched_at: datetime,
    ) -> SportsFixture:
        stmt = (
            insert(SportsFixture)
            .values(
                source_id=source_id,
                sport_id=sport_id,
                competition_id=competition_id,
                canonical_fixture_id=canonical_fixture_id,
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
                    "canonical_fixture_id": canonical_fixture_id,
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

        unique_participants: list[ProviderParticipant] = []
        seen_external_ids: set[str] = set()

        for participant in fixture.participants:
            self._validate_participant(participant)

            if participant.external_id in seen_external_ids:
                continue

            seen_external_ids.add(participant.external_id)
            unique_participants.append(participant)

        canonical_candidate = CanonicalFixtureCandidate(
            sport_slug=fixture.sport_slug,
            starts_at=fixture.starts_at,
            participants=[
                participant.name
                for participant in unique_participants
            ],
            competition_name=(
                fixture.competition.name
                if fixture.competition is not None
                else None
            ),
        )

        canonical_fixture = (
            await self.repository.resolve_canonical_fixture(
                sport_id=sport.id,
                candidate=canonical_candidate,
            )
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
            canonical_fixture_id=canonical_fixture.id,
            fixture=fixture,
            fetched_at=fetched_at,
        )

        stats.fixtures_processed += 1

        for participant in unique_participants:
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
