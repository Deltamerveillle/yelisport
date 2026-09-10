"""Maintenance helpers for historical SMS24 canonical fixture backfill."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sport import Sport
from app.models.sports_live import (
    SportsCompetitor,
    SportsDataSource,
    SportsFixture,
    SportsFixtureParticipant,
)
from app.sms24.canonical import CanonicalFixtureCandidate
from app.sms24.ingestion import SMS24IngestionRepository


@dataclass(slots=True)
class CanonicalBackfillResult:
    processed: int = 0
    resolved: int = 0
    skipped: int = 0


async def backfill_historical_canonical_fixtures(
    session: AsyncSession,
) -> CanonicalBackfillResult:
    """
    Attach historical provider observations to canonical fixtures.

    Only fixtures without canonical_fixture_id are considered.
    Incomplete fixtures are skipped rather than guessed.
    The caller owns the transaction and decides whether to commit
    or roll back.
    """

    repository = SMS24IngestionRepository(session)

    statement = (
        select(
            SportsFixture,
            Sport.slug,
            SportsDataSource.slug,
        )
        .join(
            Sport,
            Sport.id == SportsFixture.sport_id,
        )
        .join(
            SportsDataSource,
            SportsDataSource.id == SportsFixture.source_id,
        )
        .where(
            SportsFixture.canonical_fixture_id.is_(None)
        )
        .order_by(
            SportsFixture.starts_at.asc(),
            SportsFixture.id.asc(),
        )
    )

    rows = (await session.execute(statement)).all()

    result = CanonicalBackfillResult(
        processed=len(rows),
    )

    for fixture, sport_slug, _source_slug in rows:
        participant_statement = (
            select(SportsCompetitor.name)
            .join(
                SportsFixtureParticipant,
                SportsFixtureParticipant.competitor_id
                == SportsCompetitor.id,
            )
            .where(
                SportsFixtureParticipant.fixture_id == fixture.id
            )
            .order_by(
                SportsFixtureParticipant.position.asc(),
                SportsFixtureParticipant.id.asc(),
            )
        )

        participants = list(
            (
                await session.execute(participant_statement)
            ).scalars().all()
        )

        # Never guess an event identity from insufficient evidence.
        if len(participants) < 2:
            result.skipped += 1
            continue

        candidate = CanonicalFixtureCandidate(
            sport_slug=sport_slug,
            starts_at=fixture.starts_at,
            participants=participants,
            competition_name=None,
        )

        canonical = await repository.resolve_canonical_fixture(
            sport_id=fixture.sport_id,
            candidate=candidate,
        )

        fixture.canonical_fixture_id = canonical.id
        result.resolved += 1

    await session.flush()

    return result
