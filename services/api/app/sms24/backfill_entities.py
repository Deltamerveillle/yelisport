"""Caller-controlled historical backfill for the SMS24 0028 entity foundation."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sports_live import (
    SportsCanonicalCompetition,
    SportsCanonicalCompetitor,
    SportsCompetition,
    SportsCompetitor,
    SportsSeason,
)
from app.sms24.ingestion import SMS24IngestionRepository
from app.sms24.providers import ProviderCompetition, ProviderParticipant


@dataclass(slots=True)
class CanonicalEntitiesBackfillResult:
    competitions_processed: int = 0
    competitions_resolved: int = 0
    competitions_skipped: int = 0
    competitors_processed: int = 0
    competitors_resolved: int = 0
    competitors_skipped: int = 0
    seasons_processed: int = 0
    seasons_resolved: int = 0
    seasons_skipped: int = 0
    canonical_competitions_total: int = 0
    canonical_competitors_total: int = 0
    seasons_total: int = 0


async def backfill_historical_canonical_entities(
    session: AsyncSession,
) -> CanonicalEntitiesBackfillResult:
    """Attach only unlinked observations, without committing or deleting anything.

    Resolved counters count observations, including reuse of an existing identity.
    Season counters count nonblank labels on the selected competition observations.
    Totals are database-wide counts visible in the caller's transaction after flush,
    not counts of creations attributable to this invocation.

    Resolver validation failures are skipped; database errors propagate to the caller.
    An invalid season does not prevent linking its valid competition. Already linked
    observations (including their season labels) are not revisited on subsequent runs.
    The caller must commit or roll back, including for dry runs and errors.
    """
    result = CanonicalEntitiesBackfillResult()
    repository = SMS24IngestionRepository(session)
    competitions = await session.scalars(
        select(SportsCompetition)
        .where(SportsCompetition.canonical_competition_id.is_(None))
        .order_by(SportsCompetition.id)
        .with_for_update()
    )
    for observation in competitions:
        result.competitions_processed += 1
        has_season = bool(observation.season and observation.season.strip())
        if has_season:
            result.seasons_processed += 1
        try:
            canonical = await repository.resolve_canonical_competition(
                sport_id=observation.sport_id,
                source_id=observation.source_id,
                competition=ProviderCompetition(
                    jurisdiction_name=observation.jurisdiction_name,
                    external_id=observation.external_id,
                    name=observation.name,
                    country_code=observation.country_code,
                ),
            )
        except ValueError:
            result.competitions_skipped += 1
            if has_season:
                result.seasons_skipped += 1
            continue
        observation.canonical_competition_id = canonical.id
        result.competitions_resolved += 1
        if has_season:
            try:
                await repository.resolve_season(
                    canonical_competition_id=canonical.id,
                    label=observation.season,
                )
            except ValueError:
                result.seasons_skipped += 1
            else:
                result.seasons_resolved += 1

    competitors = await session.scalars(
        select(SportsCompetitor)
        .where(SportsCompetitor.canonical_competitor_id.is_(None))
        .order_by(SportsCompetitor.id)
        .with_for_update()
    )
    for observation in competitors:
        result.competitors_processed += 1
        try:
            canonical = await repository.resolve_canonical_competitor(
                sport_id=observation.sport_id,
                source_id=observation.source_id,
                participant=ProviderParticipant(
                    external_id=observation.external_id,
                    competitor_type=observation.competitor_type,
                    name=observation.name,
                    country_code=observation.country_code,
                ),
            )
        except ValueError:
            result.competitors_skipped += 1
            continue
        observation.canonical_competitor_id = canonical.id
        result.competitors_resolved += 1

    await session.flush()
    result.canonical_competitions_total = await session.scalar(
        select(func.count()).select_from(SportsCanonicalCompetition)
    )
    result.canonical_competitors_total = await session.scalar(
        select(func.count()).select_from(SportsCanonicalCompetitor)
    )
    result.seasons_total = await session.scalar(select(func.count()).select_from(SportsSeason))
    return result
