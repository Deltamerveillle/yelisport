"""API tests for public SMS24 Live endpoints."""

from datetime import datetime, timezone
import uuid

import pytest

from app.core.exceptions import NotFoundError
from app.db.session import get_db_session
from app.repositories.sms24_live_repository import (
    SMS24FixtureView,
    SMS24ParticipantView,
    SMS24SourceHealthView,
)
from app.services.sms24_live_service import SMS24LiveService


FIXTURE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
COMPETITION_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
COMPETITOR_A_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
COMPETITOR_B_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
SOURCE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")

NOW = datetime(2026, 9, 6, 20, 0, tzinfo=timezone.utc)


class FakeSession:
    pass


@pytest.fixture
def sms24_dependencies(client):
    session = FakeSession()

    async def override_db():
        yield session

    client.app.dependency_overrides[get_db_session] = override_db

    yield session

    client.app.dependency_overrides.clear()


def make_fixture() -> SMS24FixtureView:
    return SMS24FixtureView(
        id=FIXTURE_ID,
        external_id="fixture-001",
        sport_slug="football",
        sport_name="Football",
        source_slug="provider-test",
        source_name="Provider Test",
        competition_id=COMPETITION_ID,
        competition_name="SMS24 Test League",
        competition_country_code="CI",
        season="2026",
        name="Abidjan SMS - Yamoussoukro SMS",
        starts_at=NOW,
        status="live",
        live_clock="67'",
        venue="Stade SMS",
        result={"period": "second_half"},
        metadata={"coverage": "live"},
        source_updated_at=NOW,
        fetched_at=NOW,
        participants=[
            SMS24ParticipantView(
                competitor_id=COMPETITOR_A_ID,
                competitor_type="team",
                name="Abidjan SMS",
                short_name="ASM",
                country_code="CI",
                logo_url=None,
                position=0,
                role="home",
                score={"score": 2},
                result_status="leading",
            ),
            SMS24ParticipantView(
                competitor_id=COMPETITOR_B_ID,
                competitor_type="team",
                name="Yamoussoukro SMS",
                short_name="YSM",
                country_code="CI",
                logo_url=None,
                position=1,
                role="away",
                score={"score": 1},
                result_status="trailing",
            ),
        ],
    )


def test_sms24_live_returns_live_fixture(
    client,
    sms24_dependencies,
    monkeypatch,
):
    async def fake_list_live(
        self,
        *,
        sport_slug=None,
        limit=50,
        offset=0,
    ):
        assert sport_slug == "football"
        assert limit == 50
        assert offset == 0
        return [make_fixture()]

    monkeypatch.setattr(
        SMS24LiveService,
        "list_live",
        fake_list_live,
    )

    response = client.get(
        "/api/v1/sms24/live",
        params={"sport": "football"},
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1

    fixture = payload[0]

    assert fixture["id"] == str(FIXTURE_ID)
    assert fixture["status"] == "live"
    assert fixture["sport_slug"] == "football"
    assert fixture["competition_name"] == "SMS24 Test League"
    assert fixture["source_name"] == "Provider Test"

    # Provider internals must never leak through the public API.
    assert "external_id" not in fixture
    assert "metadata" not in fixture

    assert len(fixture["participants"]) == 2
    assert fixture["participants"][0]["name"] == "Abidjan SMS"
    assert fixture["participants"][0]["score"] == {"score": 2}
    assert fixture["participants"][1]["name"] == "Yamoussoukro SMS"


def test_sms24_fixture_list_filters_by_status(
    client,
    sms24_dependencies,
    monkeypatch,
):
    async def fake_list_fixtures(
        self,
        *,
        status=None,
        sport_slug=None,
        starts_from=None,
        starts_until=None,
        limit=50,
        offset=0,
    ):
        assert status == "live"
        assert sport_slug == "football"
        assert starts_from is None
        assert starts_until is None
        assert limit == 50
        assert offset == 0

        return [make_fixture()]

    monkeypatch.setattr(
        SMS24LiveService,
        "list_fixtures",
        fake_list_fixtures,
    )

    response = client.get(
        "/api/v1/sms24/fixtures",
        params={
            "sport": "football",
            "status": "live",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["id"] == str(FIXTURE_ID)
    assert payload[0]["status"] == "live"


def test_sms24_fixture_detail(
    client,
    sms24_dependencies,
    monkeypatch,
):
    async def fake_get_fixture(
        self,
        fixture_id,
    ):
        assert fixture_id == FIXTURE_ID
        return make_fixture()

    monkeypatch.setattr(
        SMS24LiveService,
        "get_fixture",
        fake_get_fixture,
    )

    response = client.get(
        f"/api/v1/sms24/fixtures/{FIXTURE_ID}"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["id"] == str(FIXTURE_ID)
    assert payload["name"] == "Abidjan SMS - Yamoussoukro SMS"
    assert payload["live_clock"] == "67'"
    assert payload["venue"] == "Stade SMS"
    assert payload["result"] == {
        "period": "second_half"
    }
    assert len(payload["participants"]) == 2


def test_sms24_fixture_detail_not_found(
    client,
    sms24_dependencies,
    monkeypatch,
):
    missing_id = uuid.UUID(
        "99999999-9999-9999-9999-999999999999"
    )

    async def fake_get_fixture(
        self,
        fixture_id,
    ):
        assert fixture_id == missing_id
        raise NotFoundError(
            "Rencontre SMS24 introuvable"
        )

    monkeypatch.setattr(
        SMS24LiveService,
        "get_fixture",
        fake_get_fixture,
    )

    response = client.get(
        f"/api/v1/sms24/fixtures/{missing_id}"
    )

    assert response.status_code == 404


def test_sms24_source_health(
    client,
    sms24_dependencies,
    monkeypatch,
):
    async def fake_list_source_health(self):
        return [
            SMS24SourceHealthView(
                id=SOURCE_ID,
                slug="provider-test",
                name="Provider Test",
                provider_type="api",
                priority=10,
                health_status="healthy",
                last_success_at=NOW,
                last_failure_at=None,
                last_checked_at=NOW,
            )
        ]

    monkeypatch.setattr(
        SMS24LiveService,
        "list_source_health",
        fake_list_source_health,
    )

    response = client.get(
        "/api/v1/sms24/sources/health"
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1

    source = payload[0]

    assert source["id"] == str(SOURCE_ID)
    assert source["slug"] == "provider-test"
    assert source["health_status"] == "healthy"
    assert source["provider_type"] == "api"
    assert "priority" not in source


def test_sms24_invalid_status_is_rejected(
    client,
    sms24_dependencies,
):
    response = client.get(
        "/api/v1/sms24/fixtures",
        params={"status": "playing"},
    )

    assert response.status_code == 422
