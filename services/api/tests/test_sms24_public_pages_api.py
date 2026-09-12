"""Public page HTTP contracts backed by per-test isolated PostgreSQL data."""

import uuid

import httpx
import pytest

from app.db.session import get_db_session
from app.main import create_app
from app.models.sports_live import SportsSeason
from tests.test_sms24_public_pages_repository_postgres import (
    add,
    canonical_competition,
    canonical_team,
    competition_observation,
    fixture,
    seed,
    standing,
    team_observation,
)
from tests.test_sms24_public_pages_repository_postgres import session as isolated_session

session = isolated_session
BASE = "/api/v1/sms24"


@pytest.fixture
async def api(session):
    app = create_app()

    async def db():
        yield session

    app.dependency_overrides[get_db_session] = db
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_public_identity_and_standings_contract(session, api):
    world = await seed(session)
    await standing(session, world, points=9)
    response = await api.get(f"{BASE}/competitions/{world.competition.id}")
    assert response.status_code == 200
    comp = response.json()
    assert comp["id"] == str(world.competition.id)
    assert comp["jurisdiction_name"] == "Scotland" and comp["country_code"] is None
    assert comp["sport_slug"] == "football"
    assert comp["selected_season_id"] is None
    assert [s["id"] for s in comp["seasons"]] == [str(world.season.id)]
    response = await api.get(f"{BASE}/teams/{world.team.id}")
    assert response.status_code == 200
    team = response.json()
    assert team["id"] == str(world.team.id)
    assert team["identity_scope"] == "provider_scoped" and team["country_code"] is None
    assert [c["id"] for c in team["competitions"]] == [str(world.competition.id)]
    for body in [comp, team]:
        serialized = str(body)
        for forbidden in ["canonical_key", "external_id", "metadata", "token", "api_key"]:
            assert forbidden not in serialized
    standings = await api.get(
        f"{BASE}/standings", params={"canonical_competitor_id": str(world.team.id)}
    )
    assert standings.status_code == 200
    assert len(standings.json()) == 1
    assert standings.json()[0]["points"] == 9
    assert standings.json()[0]["home_points"] is None
    empty = await api.get(
        f"{BASE}/standings", params={"canonical_competitor_id": str(uuid.uuid4())}
    )
    assert empty.json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("current_count", [0, 1, 2])
async def test_season_selection_and_explicit_override(session, api, current_count):
    world = await seed(session)
    await competition_observation(session, world)
    second = await add(
        session,
        SportsSeason,
        canonical_competition_id=world.competition.id,
        label="Season 9999",
        normalized_label="season 9999",
        is_current=current_count == 2,
    )
    world.season.is_current = current_count >= 1
    await session.flush()
    url = f"{BASE}/competitions/{world.competition.id}"
    response = await api.get(url)
    assert response.status_code == 200
    assert response.json()["selected_season_id"] == (
        str(world.season.id) if current_count == 1 else None
    )
    response = await api.get(url, params={"season_id": str(second.id)})
    assert response.status_code == 200
    assert response.json()["selected_season_id"] == str(second.id)
    other = await canonical_competition(session, world.sport)
    foreign = await add(
        session,
        SportsSeason,
        canonical_competition_id=other.id,
        label="2026/27",
        normalized_label="2026 27",
    )
    assert (await api.get(url, params={"season_id": str(foreign.id)})).status_code == 404
    assert (await api.get(url, params={"season_id": str(uuid.uuid4())})).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["team", "selection", "athlete", "pair", "other"])
async def test_team_type_validation(session, api, kind):
    world = await seed(session)
    team = await canonical_team(session, world.sport, competitor_type=kind)
    await team_observation(session, world, team=team)
    status = 200 if kind in {"team", "selection"} else 404
    for suffix in ["", "/fixtures"]:
        assert (await api.get(f"{BASE}/teams/{team.id}{suffix}")).status_code == status


@pytest.mark.asyncio
async def test_page_fixtures_use_explicit_canonical_ids_preserve_old_contract(session, api):
    world = await seed(session)
    comp = await competition_observation(session, world)
    team = await team_observation(session, world)
    stored = await fixture(session, world, competition=comp, participants=[team], status="live")
    comp.season = "2040"
    await session.flush()
    for route in [f"competitions/{world.competition.id}", f"teams/{world.team.id}"]:
        response = await api.get(f"{BASE}/{route}/fixtures", params={"status": "live"})
        assert response.status_code == 200
        row = response.json()[0]
        assert row["id"] == str(stored.id)
        assert row["canonical_competition_id"] == str(world.competition.id)
        assert row["canonical_season_id"] is None
        assert row["participants"][0]["canonical_competitor_id"] == str(world.team.id)
        assert "competition_id" not in row and "season" not in row
        assert "competitor_id" not in row["participants"][0]
        assert "external_id" not in str(row) and "canonical_key" not in str(row)
        assert (
            await api.get(f"{BASE}/{route}/fixtures", params={"status": "finished"})
        ).json() == []
        assert (await api.get(f"{BASE}/{route}/fixtures", params={"offset": 1})).json() == []
    legacy = (await api.get(f"{BASE}/fixtures")).json()[0]
    assert legacy["competition_id"] == str(comp.id)
    assert legacy["participants"][0]["competitor_id"] == str(team.id)
    assert legacy["season"] == "2040"
    assert "canonical_competition_id" not in legacy
    assert "canonical_competitor_id" not in legacy["participants"][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("visibility", ["orphan", "inactive_source", "inactive_sport", "missing"])
async def test_unpublished_entities_return_404(session, api, visibility):
    world = await seed(session)
    if visibility != "orphan":
        await standing(session, world)
    if visibility == "inactive_source":
        world.sources[0].is_active = False
    if visibility == "inactive_sport":
        world.sport.is_active = False
    await session.flush()
    for route, identity in [("competitions", world.competition.id), ("teams", world.team.id)]:
        if visibility == "missing":
            identity = uuid.uuid4()
        for suffix in ["", "/fixtures"]:
            assert (await api.get(f"{BASE}/{route}/{identity}{suffix}")).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["competitions", "teams"])
@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"status": "bad"}]
)
async def test_fixture_query_validation(api, route, params):
    assert (
        await api.get(f"{BASE}/{route}/{uuid.uuid4()}/fixtures", params=params)
    ).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/competitions/not-a-uuid",
        "/teams/not-a-uuid",
        "/competitions/not-a-uuid/fixtures",
        "/teams/not-a-uuid/fixtures",
        "/standings?canonical_competitor_id=42",
    ],
)
async def test_uuid_validation(api, path):
    assert (await api.get(BASE + path)).status_code == 422
