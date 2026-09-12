"""Public standings reads against disposable schemas with the real API stack."""

import uuid
from datetime import timedelta

import httpx
import pytest

from app.db.session import get_db_session
from app.main import create_app
from app.models.sports_live import SportsCanonicalCompetitor, SportsSeason
from app.models.sports_standings import SportsStanding
from app.repositories.sms24_live_repository import SMS24LiveRepository
from tests.test_sms24_standings_postgres import NOW, seed
from tests.test_sms24_standings_postgres import session as isolated_session

session = isolated_session


async def competitor(session, sport, name="Rangers"):
    item = SportsCanonicalCompetitor(
        sport_id=sport.id,
        canonical_key=uuid.uuid4().hex,
        name=name,
        normalized_name=name.casefold(),
        competitor_type="team",
        identity_scope="provider_scoped",
    )
    session.add(item)
    await session.flush()
    return item


async def standing(session, source, season, team, **values):
    item = SportsStanding(
        source_id=source.id,
        season_id=season.id,
        canonical_competitor_id=team.id,
        **{"position": 1, "fetched_at": NOW, **values},
    )
    session.add(item)
    await session.flush()
    return item


@pytest.mark.asyncio
async def test_position_order_and_distinct_same_name_identities(session):
    sport, sources, season = await seed(session)
    teams = [await competitor(session, sport) for _ in range(3)]
    stored = [
        await standing(session, sources[0], season, team, position=pos)
        for team, pos in zip(teams, [3, 1, 2], strict=True)
    ]
    rows = await SMS24LiveRepository(session).list_standings()
    assert [row.position for row in rows] == [1, 2, 3]
    assert {row.id for row in rows} == {row.id for row in stored}
    assert len({row.canonical_competitor_id for row in rows}) == 3
    assert all(row.competitor_identity_scope == "provider_scoped" for row in rows)


@pytest.mark.asyncio
@pytest.mark.parametrize("criterion", ["priority", "freshness", "uuid"])
async def test_representative_ranking_and_pagination(session, criterion):
    sport, sources, season = await seed(session)
    sources[0].priority = 10
    sources[1].priority = 20 if criterion == "priority" else 10
    team = await competitor(session, sport)
    first = await standing(
        session,
        sources[0],
        season,
        team,
        id=uuid.UUID(int=2),
        fetched_at=NOW + timedelta(hours=1) if criterion == "freshness" else NOW,
    )
    second = await standing(
        session,
        sources[1],
        season,
        team,
        id=uuid.UUID(int=1),
        fetched_at=NOW + timedelta(hours=2) if criterion == "priority" else NOW,
    )
    other = await competitor(session, sport, "Celtic")
    last = await standing(session, sources[0], season, other, position=2)
    repo = SMS24LiveRepository(session)
    expected = second if criterion == "uuid" else first
    assert [row.id for row in await repo.list_standings()] == [expected.id, last.id]
    assert [row.id for row in await repo.list_standings(limit=1)] == [expected.id]
    assert [row.id for row in await repo.list_standings(limit=1, offset=1)] == [last.id]
    assert await repo.list_standings(offset=2) == []


@pytest.mark.asyncio
async def test_inactive_primary_filtered_before_ranking(session):
    sport, sources, season = await seed(session)
    sources[0].priority, sources[1].priority = 1, 20
    sources[0].is_active = False
    team = await competitor(session, sport)
    await standing(session, sources[0], season, team)
    secondary = await standing(session, sources[1], season, team)
    rows = await SMS24LiveRepository(session).list_standings()
    assert [row.id for row in rows] == [secondary.id]
    assert rows[0].source_slug == "sportmonks"


@pytest.mark.asyncio
async def test_stage_and_group_contexts_remain_distinct(session):
    sport, sources, season = await seed(session)
    team = await competitor(session, sport)
    contexts = [
        {},
        {"stage_external_id": "stage-1"},
        {"group_name": "Group A"},
        {"group_external_id": "group-1"},
    ]
    expected = []
    for context in contexts:
        primary = await standing(session, sources[0], season, team, **context)
        await standing(session, sources[1], season, team, **context)
        expected.append(primary.id)
    sources[0].priority, sources[1].priority = 1, 20
    await session.flush()
    rows = await SMS24LiveRepository(session).list_standings()
    assert {row.id for row in rows} == set(expected)


@pytest.fixture
async def api(session):
    app = create_app()

    async def db():
        yield session

    app.dependency_overrides[get_db_session] = db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_contract_and_canonical_filters(session, api):
    sport, sources, season = await seed(session)
    team = await competitor(session, sport)
    first = await standing(session, sources[0], season, team, points=9, provider_updated_at=NOW)
    other_season = SportsSeason(
        canonical_competition_id=season.canonical_competition_id,
        label="2027",
        normalized_label="2027",
    )
    session.add(other_season)
    await session.flush()
    await standing(session, sources[0], other_season, team)
    base = "/api/v1/sms24/standings"
    response = await api.get(base, params={"season_id": str(season.id)})
    assert response.status_code == 200
    row = response.json()[0]
    assert row["id"] == str(first.id)
    assert row["season_id"] == str(season.id)
    assert row["season_label"] == "2026/27"
    assert row["competition_id"] == str(season.canonical_competition_id)
    assert row["competition_name"] == "League"
    assert row["competition_jurisdiction_name"] == "England"
    assert row["competition_country_code"] is None
    assert row["sport_slug"] == "football" and row["sport_name"] == "Football"
    assert row["canonical_competitor_id"] == str(team.id)
    assert row["competitor_name"] == "Rangers"
    assert row["competitor_identity_scope"] == "provider_scoped"
    assert row["source_slug"] == sources[0].slug
    assert row["points"] == 9 and row["home_points"] is None and row["away_points"] is None
    assert row["fetched_at"].endswith("Z") and row["provider_updated_at"].endswith("Z")
    assert "canonical_key" not in row and "external_competitor_id" not in row
    for filters, count in [
        ({"competition_id": str(season.canonical_competition_id)}, 2),
        ({"season_id": str(season.id)}, 1),
        ({"sport": "football"}, 2),
        ({"sport": "tennis"}, 0),
        ({"competition_id": str(uuid.uuid4())}, 0),
        ({"season_id": str(uuid.uuid4())}, 0),
        ({"season_id": str(season.id), "competition_id": str(uuid.uuid4())}, 0),
        (
            {
                "season_id": str(season.id),
                "competition_id": str(season.canonical_competition_id),
                "sport": "football",
            },
            1,
        ),
        ({"limit": 1, "offset": 1}, 1),
    ]:
        response = await api.get(base, params=filters)
        assert response.status_code == 200
        assert len(response.json()) == count


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"season_id": "7"},
        {"competition_id": "179"},
        {"sport": ""},
    ],
)
async def test_api_rejects_invalid_filters(api, params):
    response = await api.get("/api/v1/sms24/standings", params=params)
    assert response.status_code == 422
