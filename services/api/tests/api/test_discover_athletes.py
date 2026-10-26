"""API tests for SMS Discover athlete search."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.core.exceptions import NotFoundError
from app.db.session import get_db_session
from app.services.discover_athlete_profile_service import (
    DiscoverAthleteProfileService,
)
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
            "nationality_country_id": COUNTRY_ID,
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
            "nationality_country_id": str(COUNTRY_ID),
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



def test_discover_athlete_profile_is_public_and_returns_showcase(
    client,
    discover_athlete_dependencies,
    monkeypatch,
):
    now = datetime.now(UTC)
    discover = make_discover_result()

    async def fake_get_profile(self, athlete_id):
        assert athlete_id == ATHLETE_ID
        return {
            "athlete": {
                "id": str(discover.athlete.id),
                "sport_id": str(discover.athlete.sport_id),
                "first_name": discover.athlete.first_name,
                "last_name": discover.athlete.last_name,
                "nationality": discover.athlete.nationality,
                "country": discover.athlete.country,
                "residence_country_id": str(
                    discover.athlete.residence_country_id
                ),
                "city": discover.athlete.city,
                "biography": discover.athlete.biography,
                "created_at": discover.athlete.created_at.isoformat(),
                "updated_at": discover.athlete.updated_at.isoformat(),
            },
            "passport": {
                "id": str(discover.passport.id),
                "athlete_id": str(discover.passport.athlete_id),
                "discipline": discover.passport.discipline,
                "category": discover.passport.category,
                "position": discover.passport.position,
                "club_name": discover.passport.club_name,
                "league_name": discover.passport.league_name,
                "team_name": discover.passport.team_name,
                "height_cm": discover.passport.height_cm,
                "weight_kg": discover.passport.weight_kg,
                "dominant_side": discover.passport.dominant_side,
                "available_for_opportunities": True,
                "sporting_summary": discover.passport.sporting_summary,
                "created_at": discover.passport.created_at.isoformat(),
                "updated_at": discover.passport.updated_at.isoformat(),
            },
            "performances": [],
            "statistics": {
                "linked": True,
                "observations": [
                    {
                        "scope": "season",
                        "period_label": "2026",
                        "metrics": {"appearances": 12, "goals": 4},
                        "fetched_at": now.isoformat(),
                        "source_updated_at": None,
                    }
                ],
            },
            "videos": [],
        }

    monkeypatch.setattr(
        DiscoverAthleteProfileService,
        "get_profile",
        fake_get_profile,
    )

    response = client.get(
        f"/api/v1/discover/athletes/{ATHLETE_ID}"
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["athlete"]["id"] == str(ATHLETE_ID)
    assert "user_id" not in payload["athlete"]
    assert payload["passport"]["available_for_opportunities"] is True
    assert payload["performances"] == []
    assert payload["statistics"]["linked"] is True
    assert payload["statistics"]["observations"][0]["metrics"]["goals"] == 4
    assert payload["videos"] == []

    forbidden = {
        "identity_link_id",
        "canonical_competitor_id",
        "provider_competitor_id",
        "athlete_external_id",
        "observation_id",
        "source_id",
        "metadata",
    }
    assert forbidden.isdisjoint(
        payload["statistics"]["observations"][0].keys()
    )


def test_discover_athlete_profile_returns_404_when_not_discoverable(
    client,
    discover_athlete_dependencies,
    monkeypatch,
):
    async def fake_get_profile(self, athlete_id):
        assert athlete_id == ATHLETE_ID
        raise NotFoundError("Discover athlete not found")

    monkeypatch.setattr(
        DiscoverAthleteProfileService,
        "get_profile",
        fake_get_profile,
    )

    response = client.get(
        f"/api/v1/discover/athletes/{ATHLETE_ID}"
    )

    assert response.status_code == 404
