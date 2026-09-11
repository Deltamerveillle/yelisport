"""Historical entity backfill tests isolated in disposable PostgreSQL schemas."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.base import Base
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
from app.sms24.backfill_entities import backfill_historical_canonical_entities
from app.sms24.canonical import CanonicalFixtureCandidate
from app.sms24.ingestion import SMS24IngestionRepository
from app.sms24.providers import ProviderCompetition, ProviderParticipant


@pytest.fixture
async def session():
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                schema = f"sms24_entities_test_{uuid.uuid4().hex}"
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                # No public fallback: the historical scan can only see this test's rows.
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                tables = [
                    model.__table__
                    for model in (
                        Sport,
                        SportsDataSource,
                        SportsCanonicalCompetition,
                        SportsCanonicalCompetitor,
                        SportsSeason,
                        SportsCompetition,
                        SportsCompetitor,
                        SportsCanonicalFixture,
                        SportsFixture,
                        SportsFixtureParticipant,
                    )
                ]
                await connection.run_sync(
                    lambda conn: Base.metadata.create_all(conn, tables=tables)
                )
                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as test_session:
                    yield test_session
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


async def seed(session):
    sport = Sport(slug="test-multisport", name="Historical sport", is_active=False)
    sources = [
        SportsDataSource(slug=f"provider-{i}", name=f"Provider {i}", is_active=False)
        for i in range(2)
    ]
    session.add_all([sport, *sources])
    await session.flush()
    return sport, sources


def competition(sport, source, name="Premier League", season=None, **kwargs):
    return SportsCompetition(
        sport_id=sport.id,
        source_id=source.id,
        external_id=uuid.uuid4().hex,
        name=name,
        season=season,
        jurisdiction_name=kwargs.pop("jurisdiction_name", "England"),
        country_code=kwargs.pop("country_code", "GB"),
        **kwargs,
    )


def competitor(sport, source, name="St. Mirren", **kwargs):
    return SportsCompetitor(
        sport_id=sport.id,
        source_id=source.id,
        external_id=uuid.uuid4().hex,
        name=name,
        country_code=kwargs.pop("country_code", "GB"),
        competitor_type=kwargs.pop("competitor_type", "team"),
        **kwargs,
    )


async def count(session, model):
    return await session.scalar(select(func.count()).select_from(model))


def snapshot(row):
    # Linking may advance updated_at; all provider fields and IDs must survive.
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name not in {"canonical_competition_id", "canonical_competitor_id", "updated_at"}
    }


@pytest.mark.asyncio
async def test_cross_provider_entities_seasons_idempotence_and_fixture_preservation(session):
    sport, sources = await seed(session)
    competitions = [
        competition(sport, sources[0], season="Season 2026"),
        competition(sport, sources[1], "PREMIER  LEAGUE", "SEASON  2026"),
        competition(sport, sources[0], season="2026/27"),
        competition(sport, sources[1], season="2026-2027"),
        competition(sport, sources[0], season="Tour A"),
    ]
    competitors = [competitor(sport, sources[0]), competitor(sport, sources[1], "ST Mirren")]
    session.add_all([*competitions, *competitors])
    await session.flush()
    repo = SMS24IngestionRepository(session)
    candidate = CanonicalFixtureCandidate(
        sport_slug=sport.slug,
        starts_at=datetime(2026, 9, 10, tzinfo=UTC),
        participants=["St. Mirren", "Opponent"],
    )
    canonical_fixture = await repo.resolve_canonical_fixture(sport_id=sport.id, candidate=candidate)
    fixtures = [
        SportsFixture(
            source_id=source.id,
            sport_id=sport.id,
            external_id=f"fixture-{i}",
            competition_id=competitions[i].id,
            starts_at=candidate.starts_at,
            canonical_fixture_id=canonical_fixture.id if i == 0 else None,
        )
        for i, source in enumerate(sources)
    ]
    session.add_all(fixtures)
    await session.flush()
    participant = SportsFixtureParticipant(
        fixture_id=fixtures[0].id, competitor_id=competitors[0].id
    )
    session.add(participant)
    await session.flush()
    observations_before = [snapshot(row) for row in [*competitions, *competitors]]
    fixtures_before = [snapshot(row) for row in fixtures]
    participant_before = snapshot(participant)

    first = await backfill_historical_canonical_entities(session)
    assert (
        first.competitions_processed,
        first.competitions_resolved,
        first.competitions_skipped,
    ) == (5, 5, 0)
    assert (first.competitors_processed, first.competitors_resolved, first.competitors_skipped) == (
        2,
        2,
        0,
    )
    assert (first.seasons_processed, first.seasons_resolved, first.seasons_skipped) == (5, 5, 0)
    assert (
        first.canonical_competitions_total,
        first.canonical_competitors_total,
        first.seasons_total,
    ) == (1, 1, 4)
    assert len({row.canonical_competition_id for row in competitions}) == 1
    assert competitions[0].canonical_competition_id is not None
    assert competitors[0].canonical_competitor_id == competitors[1].canonical_competitor_id
    assert competitors[0].canonical_competitor_id is not None
    for row in [*competitions, *competitors, *fixtures, participant]:
        await session.refresh(row)
    assert [snapshot(row) for row in [*competitions, *competitors]] == observations_before
    assert [snapshot(row) for row in fixtures] == fixtures_before
    assert snapshot(participant) == participant_before
    assert (
        await repo.resolve_canonical_fixture(sport_id=sport.id, candidate=candidate)
    ).id == canonical_fixture.id
    assert await count(session, SportsCanonicalFixture) == 1

    second = await backfill_historical_canonical_entities(session)
    assert (
        second.competitions_processed,
        second.competitors_processed,
        second.seasons_processed,
    ) == (0, 0, 0)
    assert (second.competitions_resolved, second.competitors_resolved, second.seasons_resolved) == (
        0,
        0,
        0,
    )
    assert (
        second.canonical_competitions_total,
        second.canonical_competitors_total,
        second.seasons_total,
    ) == (1, 1, 4)
    # A newly encountered historical observation also reuses the same season identity.
    session.add(competition(sport, sources[1], season="season 2026"))
    third = await backfill_historical_canonical_entities(session)
    assert third.seasons_resolved == 1 and third.seasons_total == 4


@pytest.mark.asyncio
async def test_distinct_names_sports_countries_and_types_do_not_merge(session):
    sport, sources = await seed(session)
    other_sport = Sport(slug="other-sport", name="Other")
    session.add(other_sport)
    await session.flush()
    competitions = [
        competition(sport, sources[0]),
        competition(sport, sources[1], "Premier Division"),
        competition(other_sport, sources[0]),
        competition(sport, sources[0], country_code="IE", jurisdiction_name="Ireland"),
        competition(sport, sources[0], country_code=None, jurisdiction_name=None),
    ]
    competitors = [
        competitor(sport, sources[0]),
        competitor(sport, sources[1], "Saint Mirren"),
        competitor(other_sport, sources[0]),
        competitor(sport, sources[0], country_code="IE"),
        competitor(sport, sources[0], competitor_type="selection"),
        competitor(sport, sources[0], "東京"),
        competitor(sport, sources[1], "大阪"),
    ]
    session.add_all([*competitions, *competitors])
    result = await backfill_historical_canonical_entities(session)
    assert result.canonical_competitions_total == len(competitions)
    assert result.canonical_competitors_total == len(competitors)
    assert len({row.canonical_competition_id for row in competitions}) == len(competitions)
    assert len({row.canonical_competitor_id for row in competitors}) == len(competitors)


@pytest.mark.asyncio
async def test_reuses_ingestion_resolvers_and_leaves_existing_links_untouched(session):
    sport, sources = await seed(session)
    repo = SMS24IngestionRepository(session)
    canonical_competition = await repo.resolve_canonical_competition(
        source_id=sources[0].id,
        sport_id=sport.id,
        competition=ProviderCompetition(
            jurisdiction_name="England", external_id="x", name="Côte League", country_code="GB"
        ),
    )
    canonical_competitor = await repo.resolve_canonical_competitor(
        source_id=sources[0].id,
        sport_id=sport.id,
        participant=ProviderParticipant(external_id="x", name="Équipe A", country_code="GB"),
    )
    rows = [
        competition(sport, sources[0], "COTE—League"),
        competitor(sport, sources[0], "EQUIPE  A"),
    ]
    linked = [
        competition(
            sport,
            sources[1],
            "Different",
            "Do not create",
            canonical_competition_id=canonical_competition.id,
        ),
        competitor(sport, sources[1], "Different", canonical_competitor_id=canonical_competitor.id),
    ]
    session.add_all([*rows, *linked])
    await session.flush()
    timestamps = [row.updated_at for row in linked]
    result = await backfill_historical_canonical_entities(session)
    assert result.competitions_processed == result.competitors_processed == 1
    assert rows[0].canonical_competition_id == canonical_competition.id
    assert rows[1].canonical_competitor_id == canonical_competitor.id
    for row in linked:
        await session.refresh(row)
    assert [row.updated_at for row in linked] == timestamps
    assert linked[0].canonical_competition_id == canonical_competition.id
    assert linked[1].canonical_competitor_id == canonical_competitor.id
    assert result.seasons_processed == result.seasons_total == 0


@pytest.mark.asyncio
async def test_caller_rollback_restores_observations_and_removes_new_entities(session):
    sport, sources = await seed(session)
    rows = [competition(sport, sources[0], season="2026"), competitor(sport, sources[0])]
    session.add_all(rows)
    await session.commit()  # Savepoint commits the input fixture, not the test's outer transaction.
    ids = [row.id for row in rows]
    result = await backfill_historical_canonical_entities(session)
    assert (
        result.competitions_resolved == result.competitors_resolved == result.seasons_resolved == 1
    )
    await session.rollback()
    assert (await session.get(SportsCompetition, ids[0])).canonical_competition_id is None
    assert (await session.get(SportsCompetitor, ids[1])).canonical_competitor_id is None
    for model in [SportsCanonicalCompetition, SportsCanonicalCompetitor, SportsSeason]:
        assert await count(session, model) == 0
    assert await count(session, SportsCompetition) == await count(session, SportsCompetitor) == 1


@pytest.mark.asyncio
async def test_invalid_names_and_seasons_are_counted_without_guessing(session):
    sport, sources = await seed(session)
    invalid_competition = competition(sport, sources[0], "---", "2026")
    invalid_competitor = competitor(sport, sources[0], "---")
    invalid_season = competition(sport, sources[0], season="---")
    blank_season = competition(sport, sources[1], season="  ")
    session.add_all([invalid_competition, invalid_competitor, invalid_season, blank_season])
    result = await backfill_historical_canonical_entities(session)
    assert (
        result.competitions_processed,
        result.competitions_resolved,
        result.competitions_skipped,
    ) == (3, 2, 1)
    assert (
        result.competitors_processed,
        result.competitors_resolved,
        result.competitors_skipped,
    ) == (1, 0, 1)
    assert (result.seasons_processed, result.seasons_resolved, result.seasons_skipped) == (2, 0, 2)
    assert invalid_competition.canonical_competition_id is None
    assert invalid_competitor.canonical_competitor_id is None
    assert invalid_season.canonical_competition_id is not None
    assert result.seasons_total == 0
