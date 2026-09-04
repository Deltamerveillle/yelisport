"""API tests for SMS Performance."""

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.services.athlete_performance_service import (
    AthletePerformanceService,
)


USER_ID = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)
ATHLETE_ID = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)
SPORT_ID = uuid.UUID(
    "33333333-3333-3333-3333-333333333333"
)
PERFORMANCE_ID = uuid.UUID(
    "44444444-4444-4444-4444-444444444444"
)


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def performance_dependencies(client):
    session = FakeSession()

    async def override_current_user():
        return AuthUser(
            id=str(USER_ID),
            email="athlete@example.com",
        )

    async def override_db():
        yield session

    client.app.dependency_overrides[get_current_user] = (
        override_current_user
    )
    client.app.dependency_overrides[get_db_session] = (
        override_db
    )

    yield session

    client.app.dependency_overrides.clear()


def make_performance():
    now = datetime(
        2026,
        9,
        4,
        20,
        0,
        tzinfo=timezone.utc,
    )

    return SimpleNamespace(
        id=PERFORMANCE_ID,
        athlete_id=ATHLETE_ID,
        sport_id=SPORT_ID,
        discipline="Football",
        performance_type="match",
        competition_name="Championnat",
        season="2026/2027",
        performance_date=date(2026, 9, 4),
        metrics={
            "goals": 2,
            "assists": 1,
            "minutes": 90,
        },
        summary="Très bon match.",
        verification_status="declared",
        source_name="SMS athlete",
        source_url="https://example.com/result",
        created_at=now,
        updated_at=now,
    )


def test_create_performance(
    client,
    performance_dependencies,
    monkeypatch,
):
    async def fake_create(
        self,
        athlete_id,
        data,
        current_user_id,
    ):
        assert athlete_id == ATHLETE_ID
        assert current_user_id == USER_ID
        assert data.metrics["goals"] == 2
        return make_performance()

    monkeypatch.setattr(
        AthletePerformanceService,
        "create_performance",
        fake_create,
    )

    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/performances",
        json={
            "discipline": "Football",
            "performance_type": "match",
            "competition_name": "Championnat",
            "season": "2026/2027",
            "performance_date": "2026-09-04",
            "metrics": {
                "goals": 2,
                "assists": 1,
                "minutes": 90,
            },
            "summary": "Très bon match.",
            "source_name": "SMS athlete",
            "source_url": "https://example.com/result",
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["athlete_id"] == str(ATHLETE_ID)
    assert payload["sport_id"] == str(SPORT_ID)
    assert payload["verification_status"] == "declared"
    assert payload["metrics"]["goals"] == 2
    assert performance_dependencies.commits == 1


def test_athlete_cannot_submit_verification_status(
    client,
    performance_dependencies,
):
    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/performances",
        json={
            "performance_date": "2026-09-04",
            "metrics": {"goals": 2},
            "verification_status": "verified",
        },
    )

    assert response.status_code == 422


def test_performance_requires_authentication(client):
    response = client.get(
        f"/api/v1/athletes/{ATHLETE_ID}/performances"
    )

    assert response.status_code in {401, 403}


def test_list_performances(
    client,
    performance_dependencies,
    monkeypatch,
):
    async def fake_list(
        self,
        athlete_id,
        current_user_id,
    ):
        assert athlete_id == ATHLETE_ID
        assert current_user_id == USER_ID
        return [make_performance()]

    monkeypatch.setattr(
        AthletePerformanceService,
        "list_athlete_performances",
        fake_list,
    )

    response = client.get(
        f"/api/v1/athletes/{ATHLETE_ID}/performances"
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["metrics"]["assists"] == 1
    assert payload[0]["verification_status"] == "declared"
