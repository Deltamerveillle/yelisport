"""Canonical public pages in a rollback-only PostgreSQL schema per test."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import text
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
from app.models.sports_standings import SportsStanding
from app.repositories.sms24_live_repository import SMS24LiveRepository

NOW = datetime(2026, 9, 12, 12, tzinfo=UTC)


@pytest.fixture
async def session():
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                schema = f"sms24_pages_test_{uuid.uuid4().hex}"
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
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
                        SportsStanding,
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


async def add(session, model, **values):
    item = model(**values)
    session.add(item)
    await session.flush()
    return item


async def seed(session):
    sport = await add(session, Sport, slug="football", name="Football")
    sources = [
        await add(
            session,
            SportsDataSource,
            slug=f"provider-{i}",
            name=f"Provider {i}",
            priority=10 + i * 10,
        )
        for i in range(2)
    ]
    competition = await canonical_competition(session, sport)
    team = await canonical_team(session, sport)
    season = await add(
        session,
        SportsSeason,
        canonical_competition_id=competition.id,
        label="2026/27",
        normalized_label="2026 27",
    )
    return SimpleNamespace(
        sport=sport, sources=sources, competition=competition, team=team, season=season
    )


async def canonical_competition(session, sport):
    return await add(
        session,
        SportsCanonicalCompetition,
        sport_id=sport.id,
        canonical_key=uuid.uuid4().hex,
        name="League",
        normalized_name="league",
        jurisdiction_name="Scotland",
        country_code=None,
        identity_scope="verified_context",
    )


async def canonical_team(session, sport, competitor_type="team"):
    return await add(
        session,
        SportsCanonicalCompetitor,
        sport_id=sport.id,
        canonical_key=uuid.uuid4().hex,
        name="Rangers",
        normalized_name="rangers",
        identity_scope="provider_scoped",
        competitor_type=competitor_type,
    )


async def competition_observation(session, world, source=None, competition=None):
    return await add(
        session,
        SportsCompetition,
        source_id=(source or world.sources[0]).id,
        sport_id=world.sport.id,
        external_id=uuid.uuid4().hex,
        name="Provider League",
        canonical_competition_id=(competition or world.competition).id,
        season="2026/27",
    )


async def team_observation(session, world, source=None, team=None):
    return await add(
        session,
        SportsCompetitor,
        source_id=(source or world.sources[0]).id,
        sport_id=world.sport.id,
        external_id=uuid.uuid4().hex,
        name="Provider Rangers",
        canonical_competitor_id=(team or world.team).id,
    )


async def standing(session, world, source=None, team=None, season=None, **values):
    return await add(
        session,
        SportsStanding,
        source_id=(source or world.sources[0]).id,
        canonical_competitor_id=(team or world.team).id,
        season_id=(season or world.season).id,
        **{"position": 1, "fetched_at": NOW, **values},
    )


async def event(session, world):
    return await add(
        session,
        SportsCanonicalFixture,
        sport_id=world.sport.id,
        canonical_key=uuid.uuid4().hex,
        participant_signature=uuid.uuid4().hex,
        starts_at=NOW,
    )


async def fixture(
    session, world, *, source=None, competition=None, participants=(), canonical=None, **values
):
    item = await add(
        session,
        SportsFixture,
        source_id=(source or world.sources[0]).id,
        sport_id=world.sport.id,
        external_id=uuid.uuid4().hex,
        competition_id=competition.id if competition else None,
        canonical_fixture_id=canonical.id if canonical else None,
        **{"starts_at": NOW, "fetched_at": NOW, "status": "scheduled", **values},
    )
    for i, participant in enumerate(participants):
        await add(
            session,
            SportsFixtureParticipant,
            fixture_id=item.id,
            competitor_id=participant.id,
            position=i,
        )
    return item


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["observation", "fixture", "standing"])
async def test_independent_active_provenance_paths(session, path):
    world = await seed(session)
    repo = SMS24LiveRepository(session)
    assert await repo.get_competition(world.competition.id) is None
    assert await repo.get_team(world.team.id) is None
    if path == "observation":
        await competition_observation(session, world)
        await team_observation(session, world)
    elif path == "fixture":
        world.sources[1].is_active = False
        comp = await competition_observation(session, world, source=world.sources[1])
        team = await team_observation(session, world, source=world.sources[1])
        await fixture(session, world, competition=comp, participants=[team])
    else:
        await standing(session, world)
    competition = await repo.get_competition(world.competition.id)
    team = await repo.get_team(world.team.id)
    assert competition.id == world.competition.id
    assert [season.id for season in competition.seasons] == [world.season.id]
    assert team.id == world.team.id and team.identity_scope == "provider_scoped"
    if path == "observation":
        assert team.competitions == []  # Independent observations do not prove participation.
    else:
        assert [comp.id for comp in team.competitions] == [world.competition.id]
        assert [s.id for s in team.competitions[0].seasons] == (
            [world.season.id] if path == "standing" else []
        )
    world.sources[0].is_active = False
    await session.flush()
    assert await repo.get_competition(world.competition.id) is None
    assert await repo.get_team(world.team.id) is None


@pytest.mark.asyncio
async def test_inactive_sport_and_unrelated_identity_are_not_public(session):
    world = await seed(session)
    await standing(session, world)
    other = await canonical_team(session, world.sport)
    repo = SMS24LiveRepository(session)
    assert await repo.get_team(other.id) is None
    world.sport.is_active = False
    await session.flush()
    assert await repo.get_team(world.team.id) is None
    assert await repo.get_competition(world.competition.id) is None


@pytest.mark.asyncio
async def test_relations_union_by_uuid_with_only_standing_attested_seasons(session):
    world = await seed(session)
    await standing(session, world)
    comp = await competition_observation(session, world)
    participant = await team_observation(session, world)
    await fixture(session, world, competition=comp, participants=[participant])
    second = await canonical_competition(session, world.sport)  # Same name, different UUID.
    second_obs = await competition_observation(session, world, competition=second)
    await fixture(session, world, competition=second_obs, participants=[participant])
    unrelated_season = await add(
        session,
        SportsSeason,
        canonical_competition_id=second.id,
        label="Season 2027",
        normalized_label="season 2027",
    )
    result = await SMS24LiveRepository(session).get_team(world.team.id)
    relations = {relation.id: relation for relation in result.competitions}
    assert set(relations) == {world.competition.id, second.id}
    assert [s.id for s in relations[world.competition.id].seasons] == [world.season.id]
    assert relations[second.id].seasons == []
    assert unrelated_season.id != world.season.id


@pytest.mark.asyncio
@pytest.mark.parametrize("criterion", ["priority", "freshness", "uuid"])
async def test_fixture_representative_and_pagination(session, criterion):
    world = await seed(session)
    canonical = await event(session, world)
    comp = await competition_observation(session, world)
    team = await team_observation(session, world)
    first = await fixture(
        session,
        world,
        canonical=canonical,
        competition=comp,
        participants=[team],
        id=uuid.UUID(int=2),
        fetched_at=NOW + timedelta(hours=1) if criterion == "freshness" else NOW,
    )
    second = await fixture(
        session,
        world,
        source=world.sources[1],
        canonical=canonical,
        competition=comp,
        participants=[team],
        id=uuid.UUID(int=1),
        fetched_at=NOW + timedelta(hours=2) if criterion == "priority" else NOW,
    )
    if criterion != "priority":
        world.sources[1].priority = world.sources[0].priority
    legacy = [
        await fixture(
            session,
            world,
            competition=comp,
            participants=[team],
            starts_at=NOW + timedelta(days=1),
            id=uuid.UUID(int=i),
        )
        for i in [3, 4]
    ]
    await session.flush()
    repo = SMS24LiveRepository(session)
    expected = [second.id if criterion == "uuid" else first.id, *[f.id for f in legacy]]
    for filters in [
        {"canonical_competitor_id": world.team.id},
        {"canonical_competition_id": world.competition.id},
    ]:
        assert [f.id for f in await repo.list_fixtures(**filters)] == expected
        assert [f.id for f in await repo.list_fixtures(**filters, limit=1, offset=1)] == [
            legacy[0].id
        ]
        assert await repo.list_fixtures(**filters, offset=3) == []


@pytest.mark.asyncio
async def test_team_exists_filter_before_ranking_no_participant_multiplication(session):
    world = await seed(session)
    other = await canonical_team(session, world.sport)
    wrong = await team_observation(session, world, team=other)
    right = [await team_observation(session, world) for _ in range(2)]
    canonical = await event(session, world)
    await fixture(session, world, participants=[wrong], canonical=canonical)
    secondary = await fixture(
        session, world, source=world.sources[1], participants=right, canonical=canonical
    )
    repo = SMS24LiveRepository(session)
    assert [f.id for f in await repo.list_fixtures(canonical_competitor_id=world.team.id)] == [
        secondary.id
    ]
    assert await repo.list_fixtures(canonical_competitor_id=world.team.id, offset=1) == []
    assert len(await repo.list_fixtures(canonical_competitor_id=other.id)) == 1


@pytest.mark.asyncio
async def test_inactive_primary_excluded_before_ranking(session):
    world = await seed(session)
    team = await team_observation(session, world)
    canonical = await event(session, world)
    await fixture(session, world, participants=[team], canonical=canonical)
    secondary = await fixture(
        session, world, source=world.sources[1], participants=[team], canonical=canonical
    )
    world.sources[0].is_active = False
    await session.flush()
    result = await SMS24LiveRepository(session).list_fixtures(canonical_competitor_id=world.team.id)
    assert [f.id for f in result] == [secondary.id]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["live", "finished", "scheduled"])
async def test_status_and_date_filters(session, status):
    world = await seed(session)
    team = await team_observation(session, world)
    expected = None
    for i, state in enumerate(["live", "finished", "scheduled"]):
        item = await fixture(
            session, world, participants=[team], status=state, starts_at=NOW + timedelta(hours=i)
        )
        if state == status:
            expected = item
    repo = SMS24LiveRepository(session)
    rows = await repo.list_fixtures(canonical_competitor_id=world.team.id, statuses={status})
    assert [row.id for row in rows] == [expected.id]
    assert (
        await repo.list_fixtures(
            canonical_competitor_id=world.team.id, starts_from=NOW + timedelta(days=1)
        )
        == []
    )


@pytest.mark.asyncio
async def test_standings_team_filter_keeps_contexts_and_exact_identities(session):
    world = await seed(session)
    other = await canonical_team(session, world.sport)
    await standing(session, world, team=other)
    for context in [{}, {"stage_external_id": "final"}, {"group_name": "Group A"}]:
        await standing(session, world, **context)
        await standing(session, world, source=world.sources[1], **context)
    rows = await SMS24LiveRepository(session).list_standings(canonical_competitor_id=world.team.id)
    assert len(rows) == 3
    assert all(row.canonical_competitor_id == world.team.id for row in rows)
    assert all(row.source_slug == world.sources[0].slug for row in rows)
    assert (
        len(await SMS24LiveRepository(session).list_standings(canonical_competitor_id=other.id))
        == 1
    )


@pytest.mark.asyncio
async def test_fixture_season_remains_unknown_after_provider_season_mutation(session):
    world = await seed(session)
    comp = await competition_observation(session, world)
    await fixture(session, world, competition=comp)
    repo = SMS24LiveRepository(session)
    for label in ["2026/27", "Season 2040"]:
        comp.season = label
        await session.flush()
        rows = await repo.list_fixtures(canonical_competition_id=world.competition.id)
        assert rows[0].canonical_season_id is None
        assert rows[0].canonical_competition_id == world.competition.id
        assert rows[0].season == label  # Legacy contract remains an observation label.


@pytest.mark.asyncio
async def test_team_relations_exclude_cross_sport_standings_and_fixtures(session):
    world = await seed(session)
    await standing(session, world)
    other_sport = await add(session, Sport, slug="basketball", name="Basketball")
    other_competition = await canonical_competition(session, other_sport)
    other_season = await add(
        session,
        SportsSeason,
        canonical_competition_id=other_competition.id,
        label="2026/27",
        normalized_label="2026 27",
    )
    # Deliberately inconsistent FK-valid observations must not become public relations.
    await standing(session, world, season=other_season)
    observation = await competition_observation(session, world, competition=other_competition)
    participant = await team_observation(session, world)
    await fixture(session, world, competition=observation, participants=[participant])

    result = await SMS24LiveRepository(session).get_team(world.team.id)

    assert result is not None
    assert [competition.id for competition in result.competitions] == [world.competition.id]
    assert [season.id for competition in result.competitions for season in competition.seasons] == [
        world.season.id
    ]
