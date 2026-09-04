"""API tests for SMS Nations athlete discovery."""

import uuid
from types import SimpleNamespace

import pytest

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.repositories.sms_nations_repository import (
    SMSNationAthleteRow,
    SMSNationsSearchResult,
)
from app.schemas.auth import AuthUser
from app.services.sms_nations_service import SMSNationsService


USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ATHLETE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
SPORT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
CI_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
FR_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
VIDEO_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")


class FakeSession:
    pass


@pytest.fixture
def sms_nations_dependencies(client):
    session = FakeSession()

    async def override_current_user():
        return AuthUser(
            id=str(USER_ID),
            email="recruiter@example.com",
        )

    async def override_db():
        yield session

    client.app.dependency_overrides[get_current_user] = (
        override_current_user
    )
    client.app.dependency_overrides[get_db_session] = override_db

    yield session

    client.app.dependency_overrides.clear()


def make_row():
    return SMSNationAthleteRow(
        athlete_id=ATHLETE_ID,
        first_name="Awa",
        last_name="Kouassi",
        city="Paris",
        avatar_url="https://example.com/awa.jpg",
        sport_id=SPORT_ID,
        sport_slug="football",
        sport_name="Football",
        residence_country_id=FR_ID,
        residence_country_iso2="FR",
        residence_country_name="France",
        discipline="Football",
        category="Senior",
        position="Attaquant",
        club_name="Paris Talent FC",
        league_name="Ligue 1",
        team_name=None,
        available_for_opportunities=True,
        eligibility_country_id=CI_ID,
        eligibility_status="verified",
        eligibility_is_primary=True,
        discover_video_id=VIDEO_ID,
        discover_video_url="https://example.com/video.mp4",
        discover_thumbnail_url="https://example.com/thumb.jpg",
        discover_caption="Attaquant ivoirien en France",
        discover_duration_seconds=20,
    )


def test_sms_nations_search_success(
    client,
    sms_nations_dependencies,
    monkeypatch,
):
    async def fake_search(self, **kwargs):
        assert kwargs["eligibility_country_id"] == CI_ID
        assert kwargs["residence_country_id"] == FR_ID
        assert kwargs["sport_id"] == SPORT_ID
        assert kwargs["position"] == "attaquant"
        assert kwargs["available_for_opportunities"] is True
        assert kwargs["eligibility_status"] == "verified"
        assert kwargs["limit"] == 24
        assert kwargs["offset"] == 0

        return SMSNationsSearchResult(
            items=[make_row()],
            total=1,
            limit=24,
            offset=0,
        )

    monkeypatch.setattr(
        SMSNationsService,
        "search_athletes",
        fake_search,
    )

    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "eligibility_country_id": str(CI_ID),
            "residence_country_id": str(FR_ID),
            "sport_id": str(SPORT_ID),
            "position": "attaquant",
            "available_for_opportunities": "true",
            "eligibility_status": "verified",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["total"] == 1
    assert payload["limit"] == 24
    assert payload["offset"] == 0
    assert len(payload["items"]) == 1

    athlete = payload["items"][0]

    assert athlete["athlete_id"] == str(ATHLETE_ID)
    assert athlete["first_name"] == "Awa"
    assert athlete["avatar_url"] == "https://example.com/awa.jpg"
    assert athlete["sport_slug"] == "football"
    assert athlete["residence_country_iso2"] == "FR"
    assert athlete["eligibility_country_id"] == str(CI_ID)
    assert athlete["eligibility_status"] == "verified"
    assert athlete["discover_video_id"] == str(VIDEO_ID)


def test_sms_nations_response_exposes_no_personal_contacts(
    client,
    sms_nations_dependencies,
    monkeypatch,
):
    async def fake_search(self, **kwargs):
        return SMSNationsSearchResult(
            items=[make_row()],
            total=1,
            limit=24,
            offset=0,
        )

    monkeypatch.setattr(
        SMSNationsService,
        "search_athletes",
        fake_search,
    )

    response = client.get("/api/v1/sms-nations/athletes")

    assert response.status_code == 200

    athlete = response.json()["items"][0]

    assert "email" not in athlete
    assert "phone" not in athlete
    assert "whatsapp" not in athlete
    assert "user_id" not in athlete


def test_sms_nations_rejects_invalid_eligibility_status(
    client,
    sms_nations_dependencies,
):
    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "eligibility_status": "approved",
        },
    )

    assert response.status_code == 422


def test_sms_nations_rejects_limit_above_100(
    client,
    sms_nations_dependencies,
):
    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "limit": 101,
        },
    )

    assert response.status_code == 422


def test_sms_nations_rejects_negative_offset(
    client,
    sms_nations_dependencies,
):
    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "offset": -1,
        },
    )

    assert response.status_code == 422


def test_sms_nations_requires_authentication(client):
    response = client.get(
        "/api/v1/sms-nations/athletes"
    )

    assert response.status_code in {401, 403}


def test_age_range_is_forwarded_to_service(
    client,
    sms_nations_dependencies,
    monkeypatch,
):
    captured = {}

    async def fake_search(self, **kwargs):
        captured.update(kwargs)

        return SMSNationsSearchResult(
            items=[],
            total=0,
            limit=kwargs["limit"],
            offset=kwargs["offset"],
        )

    monkeypatch.setattr(
        SMSNationsService,
        "search_athletes",
        fake_search,
    )

    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "min_age": 16,
            "max_age": 18,
        },
    )

    assert response.status_code == 200
    assert captured["min_age"] == 16
    assert captured["max_age"] == 18


def test_invalid_age_range_returns_422(
    client,
    sms_nations_dependencies,
):
    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "min_age": 20,
            "max_age": 16,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "min_age must be less than or equal to max_age"
    )


def test_league_filter_is_forwarded_to_service(
    client,
    sms_nations_dependencies,
    monkeypatch,
):
    captured = {}

    async def fake_search(self, **kwargs):
        captured.update(kwargs)

        return SMSNationsSearchResult(
            items=[],
            total=0,
            limit=kwargs["limit"],
            offset=kwargs["offset"],
        )

    monkeypatch.setattr(
        SMSNationsService,
        "search_athletes",
        fake_search,
    )

    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={"league": "Ligue 1"},
    )

    assert response.status_code == 200
    assert captured["league"] == "Ligue 1"



def test_talent_filters_are_forwarded_to_service(
    client,
    sms_nations_dependencies,
    monkeypatch,
):
    from decimal import Decimal

    captured = {}

    async def fake_search(self, **kwargs):
        captured.update(kwargs)

        return SMSNationsSearchResult(
            items=[],
            total=0,
            limit=kwargs["limit"],
            offset=kwargs["offset"],
        )

    monkeypatch.setattr(
        SMSNationsService,
        "search_athletes",
        fake_search,
    )

    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "talent_evaluated": "true",
            "min_talent_score": "70",
            "max_talent_score": "90",
        },
    )

    assert response.status_code == 200
    assert captured["talent_evaluated"] is True
    assert captured["min_talent_score"] == Decimal("70")
    assert captured["max_talent_score"] == Decimal("90")


def test_invalid_talent_score_range_returns_422(
    client,
    sms_nations_dependencies,
):
    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "min_talent_score": "90",
            "max_talent_score": "70",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "min_talent_score must be less than or equal "
        "to max_talent_score"
    )


@pytest.mark.parametrize(
    "parameter,value",
    [
        ("min_talent_score", "-1"),
        ("min_talent_score", "101"),
        ("max_talent_score", "-1"),
        ("max_talent_score", "101"),
    ],
)
def test_talent_score_must_be_between_zero_and_100(
    client,
    sms_nations_dependencies,
    parameter,
    value,
):
    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={parameter: value},
    )

    assert response.status_code == 422


def test_sms_nations_response_exposes_talent_aggregate(
    client,
    sms_nations_dependencies,
    monkeypatch,
):
    from datetime import datetime, timezone
    from decimal import Decimal

    row = make_row()
    row.talent_evaluated = True
    row.talent_score = Decimal("80.00")
    row.talent_completed_at = datetime(
        2026,
        9,
        4,
        18,
        30,
        tzinfo=timezone.utc,
    )

    async def fake_search(self, **kwargs):
        return SMSNationsSearchResult(
            items=[row],
            total=1,
            limit=24,
            offset=0,
        )

    monkeypatch.setattr(
        SMSNationsService,
        "search_athletes",
        fake_search,
    )

    response = client.get(
        "/api/v1/sms-nations/athletes"
    )

    assert response.status_code == 200

    athlete = response.json()["items"][0]

    assert athlete["talent_evaluated"] is True
    assert float(athlete["talent_score"]) == 80.0
    assert athlete["talent_completed_at"] is not None

    assert "evaluator_user_id" not in athlete
    assert "comments" not in athlete
    assert "recommendation" not in athlete
    assert "scores" not in athlete



def test_performance_filters_are_forwarded_to_service(
    client,
    sms_nations_dependencies,
    monkeypatch,
):
    from datetime import date
    from decimal import Decimal

    captured = {}

    async def fake_search(self, **kwargs):
        captured.update(kwargs)

        return SMSNationsSearchResult(
            items=[],
            total=0,
            limit=kwargs["limit"],
            offset=kwargs["offset"],
        )

    monkeypatch.setattr(
        SMSNationsService,
        "search_athletes",
        fake_search,
    )

    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "performance_metric": "goals",
            "min_performance_value": "10",
            "max_performance_value": "30",
            "performance_verification_status": "verified",
            "performance_competition": "Ligue 1",
            "performance_since": "2026-01-01",
            "performance_until": "2026-12-31",
        },
    )

    assert response.status_code == 200

    assert captured["performance_metric"] == "goals"
    assert captured["min_performance_value"] == Decimal("10")
    assert captured["max_performance_value"] == Decimal("30")
    assert (
        captured["performance_verification_status"]
        == "verified"
    )
    assert captured["performance_competition"] == "Ligue 1"
    assert captured["performance_since"] == date(2026, 1, 1)
    assert captured["performance_until"] == date(2026, 12, 31)


def test_performance_value_requires_metric(
    client,
    sms_nations_dependencies,
):
    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "min_performance_value": "10",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "performance_metric is required when filtering "
        "by performance value"
    )


def test_invalid_performance_metric_name_returns_422(
    client,
    sms_nations_dependencies,
):
    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "performance_metric": "goals->evil",
        },
    )

    assert response.status_code == 422


def test_invalid_performance_value_range_returns_422(
    client,
    sms_nations_dependencies,
):
    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "performance_metric": "goals",
            "min_performance_value": "30",
            "max_performance_value": "10",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "min_performance_value must be less than or equal "
        "to max_performance_value"
    )


def test_invalid_performance_date_range_returns_422(
    client,
    sms_nations_dependencies,
):
    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "performance_since": "2026-12-31",
            "performance_until": "2026-01-01",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "performance_since must be less than or equal "
        "to performance_until"
    )


def test_invalid_performance_verification_status_returns_422(
    client,
    sms_nations_dependencies,
):
    response = client.get(
        "/api/v1/sms-nations/athletes",
        params={
            "performance_verification_status": "approved",
        },
    )

    assert response.status_code == 422
