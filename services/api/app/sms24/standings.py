"""Transactional ingestion of normalized standings into existing SMS24 identities."""

import uuid
from dataclasses import dataclass, fields

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sports_live import (
    SportsCanonicalCompetition,
    SportsCanonicalCompetitor,
    SportsCompetition,
    SportsCompetitor,
    SportsDataSource,
    SportsSeason,
)
from app.models.sports_standings import SportsStanding
from app.sms24.ingestion import SMS24IngestionRepository
from app.sms24.providers.base import ProviderParticipant
from app.sms24.providers.standings import ProviderStanding, ProviderStandingsResult
from app.sms24.providers.standings_normalization import validate_standing


@dataclass(slots=True)
class StandingsIngestionResult:
    rows_processed: int = 0
    rows_upserted: int = 0


class SMS24StandingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _competitor_id(
        self,
        *,
        source_id: uuid.UUID,
        sport_id: uuid.UUID,
        participant: ProviderParticipant,
    ) -> uuid.UUID:
        observation = await self.session.scalar(
            select(SportsCompetitor).where(
                SportsCompetitor.source_id == source_id,
                SportsCompetitor.external_id == participant.external_id,
            )
        )
        if observation is not None:
            if observation.sport_id != sport_id:
                raise ValueError("Standings participant belongs to a different sport")
            if observation.canonical_competitor_id is not None:
                canonical = await self.session.get(
                    SportsCanonicalCompetitor,
                    observation.canonical_competitor_id,
                )
                if canonical is None or canonical.sport_id != sport_id:
                    raise ValueError("Standings participant has an incompatible canonical link")
                return canonical.id
            # Preserve the existing provider observation's metadata and reliable context.
            participant = ProviderParticipant(
                external_id=observation.external_id,
                name=observation.name,
                competitor_type=observation.competitor_type,
                country_code=observation.country_code,
            )
        repository = SMS24IngestionRepository(self.session)
        canonical = await repository.resolve_canonical_competitor(
            source_id=source_id,
            sport_id=sport_id,
            participant=participant,
        )
        if observation is not None:
            observation.canonical_competitor_id = canonical.id
        # Unknown participants are resolved through the same canonical architecture.
        # Without a provider observation, the scoped key still uses source + external ID.
        return canonical.id

    async def ingest(
        self,
        *,
        source_id: uuid.UUID,
        season_id: uuid.UUID,
        result: ProviderStandingsResult,
    ) -> StandingsIngestionResult:
        """Upsert a batch mapped by the caller to an existing canonical season.

        No commit, rollback, deletion, season inference or fuzzy matching. The caller
        owns the transaction and must roll back on errors. Round/rule/position are
        mutable metadata, not snapshots or additional uniqueness dimensions.
        """
        if result.fetched_at.tzinfo is None or result.fetched_at.utcoffset() is None:
            raise ValueError("Standings fetched_at must be timezone-aware")
        source = await self.session.get(SportsDataSource, source_id)
        season = await self.session.get(SportsSeason, season_id)
        if source is None or season is None:
            raise ValueError("Standings require an existing source and canonical season")
        competition = await self.session.get(
            SportsCanonicalCompetition, season.canonical_competition_id
        )
        if competition is None:
            raise ValueError("Standings season requires a canonical competition")
        for row in result.rows:
            validate_standing(row)
        for field in ("external_competition_id", "external_season_id"):
            if (
                len({getattr(row, field) for row in result.rows if getattr(row, field) is not None})
                > 1
            ):
                raise ValueError("Standings batch contains mixed provider seasons or competitions")
        stats = StandingsIngestionResult()
        for row in result.rows:
            if row.external_competition_id is not None:
                observation = await self.session.scalar(
                    select(SportsCompetition).where(
                        SportsCompetition.source_id == source_id,
                        SportsCompetition.external_id == row.external_competition_id,
                    )
                )
                if observation is not None and (
                    observation.sport_id != competition.sport_id
                    or (
                        observation.canonical_competition_id is not None
                        and observation.canonical_competition_id != competition.id
                    )
                ):
                    raise ValueError(
                        "Standings provider league conflicts with the requested season"
                    )
            stats.rows_processed += 1
            competitor_id = await self._competitor_id(
                source_id=source_id,
                sport_id=competition.sport_id,
                participant=row.participant,
            )
            values = {
                field.name: getattr(row, field.name)
                for field in fields(ProviderStanding)
                if field.name != "participant"
            }
            values.update(
                source_id=source_id,
                season_id=season_id,
                canonical_competitor_id=competitor_id,
                external_competitor_id=row.participant.external_id,
                fetched_at=result.fetched_at,
            )
            statement = insert(SportsStanding).values(**values)
            updates = {
                name: getattr(statement.excluded, name)
                for name in values
                if name not in {"source_id", "season_id", "canonical_competitor_id"}
            }
            updates["updated_at"] = func.now()
            await self.session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_sports_standings_observation",
                    set_=updates,
                )
            )
            stats.rows_upserted += 1
        await self.session.flush()
        return stats


class StandingsIngestionService:
    """Service boundary reusing the standings repository and caller's transaction."""

    def __init__(self, repository: SMS24StandingsRepository) -> None:
        self.repository = repository

    async def ingest_provider_result(
        self,
        *,
        source_id: uuid.UUID,
        season_id: uuid.UUID,
        result: ProviderStandingsResult,
    ) -> StandingsIngestionResult:
        return await self.repository.ingest(source_id=source_id, season_id=season_id, result=result)
