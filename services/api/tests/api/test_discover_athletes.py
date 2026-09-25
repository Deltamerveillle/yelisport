"""API tests for SMS Discover athlete search."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.db.session import get_db_session
from app.services.discover_athlete_service import DiscoverAthleteService

ATHLETE_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
SPORT_ID = uuid.uuid4()
COUNTRY_ID = uuid.uuid4()
PASSPORT_ID = uuid.uuid4()


class FakeSession:
    pass


def make_discover_result():
    now = datetime.now(UTC)

    athlete = SimpleNamespace(
        id=ATHLETE_ID,
        user_id=USER_ID,
        sport_id=SPORT_ID,
        first_name="Awa",
        last_name="Koné",
        nationality="Ivorian",
        country="Côte d'Ivoire",
        residence_country_id=COUNTRY_ID,
        city="Abidjan",
        biography="Young football talent",
        created_at=now,
        updated_at=now,
    )

    passport = SimpleNamespace(
        id=PASSPORT_ID,
        athlete_id=ATHLETE_ID,
        discipline="Football",
        category="Senior",
        position="Forward",
        club_name="Abidjan Stars",
        league_name="Premier League",
        team_name="Stars A",
        height_cm=175,
        weight_kg=65,
        dominant_side="right",
        available_for_opportunities=True,
        sporting_summary="Fast attacking player",
        created_at=now,
        updated_at=now,
    )

    return SimpleNamespace(
        athlete=athlete,
        passport=passport,
    )


@pytest.fixture
def discover_athlete_dependencies(client):
    session = FakeSession()

    async def override_db():
        yield session

    client.app.dependency_overrides[get_db_session] = override_db

    yield session

    client.app.dependency_overrides.clear()


def test_discover_athletes_is_public_and_returns_projection(
    client,
    discover_athlete_dependencies,
    monkeypatch,
):
    async def fake_search(self, **kwargs):
        assert kwargs["limit"] == 50
        assert kwargs["offset"] == 0
        return [make_discover_result()]

    monkeypatch.setattr(
        DiscoverAthleteService,
        "search",
        fake_search,
    )

    response = client.get("/api/v1/discover/athletes")

    assert response.status_code == 200

    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["athlete"]["id"] == str(ATHLETE_ID)
    assert payload[0]["athlete"]["first_name"] == "Awa"
    assert "user_id" not in payload[0]["athlete"]
    assert payload[0]["passport"]["athlete_id"] == str(ATHLETE_ID)
    assert payload[0]["passport"]["available_for_opportunities"] is True


def test_discover_athletes_forwards_filters_and_pagination(
    client,
    discover_athlete_dependencies,
    monkeypatch,
):
    async def fake_search(self, **kwargs):
        assert kwargs == {
            "sport_id": SPORT_ID,
            "residence_country_id": COUNTRY_ID,
            "discipline": "Football",
            "category": "Senior",
            "position": "Forward",
            "club_name": "Abidjan Stars",
            "league_name": "Premier League",
            "team_name": "Stars A",
            "limit": 25,
            "offset": 10,
        }
        return []

    monkeypatch.setattr(
        DiscoverAthleteService,
        "search",
        fake_search,
    )

    response = client.get(
        "/api/v1/discover/athletes",
        params={
            "sport_id": str(SPORT_ID),
            "residence_country_id": str(COUNTRY_ID),
            "discipline": "Football",
            "category": "Senior",
            "position": "Forward",
            "club_name": "Abidjan Stars",
            "league_name": "Premier League",
            "team_name": "Stars A",
            "limit": 25,
            "offset": 10,
        },
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("limit", 0),
        ("limit", 101),
        ("offset", -1),
    ],
)
def test_discover_athletes_rejects_invalid_pagination(
    client,
    discover_athlete_dependencies,
    parameter,
    value,
):
    response = client.get(
        "/api/v1/discover/athletes",
        params={parameter: value},
    )

    assert response.status_code == 422
