import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.services.athlete_passport_service import AthletePassportService


USER_ID = uuid.UUID("28bbf25e-8d42-4a0a-8bc8-0f41be0fc114")
OTHER_USER_ID = uuid.UUID("a451c6f7-b023-4bef-a5a1-f84caa15a2ac")
ATHLETE_ID = uuid.UUID("f42cc315-a4b8-4da5-9f7b-c1094cae2658")
PASSPORT_ID = uuid.UUID("6f4a1b7e-5b93-4f63-a2c1-91c66df352b0")


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def passport_object(
    *,
    passport_id: uuid.UUID = PASSPORT_ID,
    athlete_id: uuid.UUID = ATHLETE_ID,
    discipline: str | None = "Football",
    category: str | None = "Senior",
    position: str | None = "Milieu",
    available_for_opportunities: bool = True,
):
    now = datetime.now(UTC)

    return SimpleNamespace(
        id=passport_id,
        athlete_id=athlete_id,
        discipline=discipline,
        category=category,
        position=position,
        club_name="SMS Abidjan",
        league_name="Ligue 1 Côte d’Ivoire",
        team_name="Équipe A",
        height_cm=190,
        weight_kg=85,
        dominant_side="Droit",
        available_for_opportunities=available_for_opportunities,
        sporting_summary="Passeport sportif SMS",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def passport_dependencies(client: TestClient):
    session = FakeSession()

    async def override_current_user():
        return AuthUser(
            id=str(USER_ID),
            email="athlete@example.com",
        )

    async def override_db():
        yield session

    client.app.dependency_overrides[get_current_user] = override_current_user
    client.app.dependency_overrides[get_db_session] = override_db

    yield session

    client.app.dependency_overrides.clear()


def test_owner_can_create_passport(
    client: TestClient,
    passport_dependencies,
    monkeypatch,
) -> None:
    captured = {}

    async def fake_create(self, athlete_id, data, current_user_id):
        captured["athlete_id"] = athlete_id
        captured["current_user_id"] = current_user_id
        captured["discipline"] = data.discipline
        return passport_object(athlete_id=athlete_id)

    monkeypatch.setattr(
        AthletePassportService,
        "create_passport",
        fake_create,
    )

    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/passport",
        json={
            "discipline": "Football",
            "category": "Senior",
            "position": "Milieu",
            "club_name": "SMS Abidjan",
            "league_name": "Ligue 1 Côte d’Ivoire",
            "team_name": "Équipe A",
            "height_cm": 190,
            "weight_kg": 85,
            "dominant_side": "Droit",
            "available_for_opportunities": True,
            "sporting_summary": "Passeport sportif SMS",
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 201
    assert response.json()["athlete_id"] == str(ATHLETE_ID)
    assert captured["athlete_id"] == ATHLETE_ID
    assert captured["current_user_id"] == USER_ID
    assert captured["discipline"] == "Football"
    assert passport_dependencies.committed is True


def test_payload_cannot_choose_athlete_id(
    client: TestClient,
    passport_dependencies,
    monkeypatch,
) -> None:
    called = {"value": False}

    async def fake_create(self, athlete_id, data, current_user_id):
        called["value"] = True
        return passport_object()

    monkeypatch.setattr(
        AthletePassportService,
        "create_passport",
        fake_create,
    )

    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/passport",
        json={
            "athlete_id": str(uuid.uuid4()),
            "discipline": "Football",
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 422
    assert called["value"] is False


def test_invalid_measurements_return_422(
    client: TestClient,
    passport_dependencies,
) -> None:
    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/passport",
        json={
            "height_cm": 0,
            "weight_kg": 501,
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 422


def test_duplicate_passport_returns_409(
    client: TestClient,
    passport_dependencies,
    monkeypatch,
) -> None:
    async def fake_create(self, athlete_id, data, current_user_id):
        raise ConflictError(
            "SMS Passport already exists for this athlete"
        )

    monkeypatch.setattr(
        AthletePassportService,
        "create_passport",
        fake_create,
    )

    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/passport",
        json={"discipline": "Football"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 409
    assert passport_dependencies.rolled_back is True


def test_non_owner_cannot_create_passport(
    client: TestClient,
    passport_dependencies,
    monkeypatch,
) -> None:
    async def fake_create(self, athlete_id, data, current_user_id):
        raise ForbiddenError(
            "You do not have permission to modify this athlete passport"
        )

    monkeypatch.setattr(
        AthletePassportService,
        "create_passport",
        fake_create,
    )

    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/passport",
        json={"discipline": "Football"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 403
    assert passport_dependencies.rolled_back is True


def test_get_passport(
    client: TestClient,
    passport_dependencies,
    monkeypatch,
) -> None:
    async def fake_get(self, athlete_id):
        assert athlete_id == ATHLETE_ID
        return passport_object()

    monkeypatch.setattr(
        AthletePassportService,
        "get_passport",
        fake_get,
    )

    response = client.get(
        f"/api/v1/athletes/{ATHLETE_ID}/passport",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(PASSPORT_ID)
    assert response.json()["athlete_id"] == str(ATHLETE_ID)


def test_missing_passport_returns_404(
    client: TestClient,
    passport_dependencies,
    monkeypatch,
) -> None:
    async def fake_get(self, athlete_id):
        raise NotFoundError("SMS Passport not found")

    monkeypatch.setattr(
        AthletePassportService,
        "get_passport",
        fake_get,
    )

    response = client.get(
        f"/api/v1/athletes/{ATHLETE_ID}/passport",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 404


def test_owner_can_update_passport(
    client: TestClient,
    passport_dependencies,
    monkeypatch,
) -> None:
    captured = {}

    async def fake_update(self, athlete_id, data, current_user_id):
        captured["athlete_id"] = athlete_id
        captured["current_user_id"] = current_user_id
        return passport_object(
            position=data.position or "Milieu",
        )

    monkeypatch.setattr(
        AthletePassportService,
        "update_passport",
        fake_update,
    )

    response = client.put(
        f"/api/v1/athletes/{ATHLETE_ID}/passport",
        json={"position": "Attaquant"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json()["position"] == "Attaquant"
    assert captured["athlete_id"] == ATHLETE_ID
    assert captured["current_user_id"] == USER_ID
    assert passport_dependencies.committed is True


def test_update_cannot_change_athlete_id(
    client: TestClient,
    passport_dependencies,
) -> None:
    response = client.put(
        f"/api/v1/athletes/{ATHLETE_ID}/passport",
        json={
            "athlete_id": str(uuid.uuid4()),
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 422


def test_update_rejects_null_opportunity_flag(
    client: TestClient,
    passport_dependencies,
) -> None:
    response = client.put(
        f"/api/v1/athletes/{ATHLETE_ID}/passport",
        json={
            "available_for_opportunities": None,
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 422


def test_non_owner_cannot_update_passport(
    client: TestClient,
    passport_dependencies,
    monkeypatch,
) -> None:
    async def fake_update(self, athlete_id, data, current_user_id):
        raise ForbiddenError(
            "You do not have permission to modify this athlete passport"
        )

    monkeypatch.setattr(
        AthletePassportService,
        "update_passport",
        fake_update,
    )

    response = client.put(
        f"/api/v1/athletes/{ATHLETE_ID}/passport",
        json={"position": "Interdit"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 403
    assert passport_dependencies.rolled_back is True


def test_owner_can_delete_passport(
    client: TestClient,
    passport_dependencies,
    monkeypatch,
) -> None:
    captured = {}

    async def fake_delete(self, athlete_id, current_user_id):
        captured["athlete_id"] = athlete_id
        captured["current_user_id"] = current_user_id
        return True

    monkeypatch.setattr(
        AthletePassportService,
        "delete_passport",
        fake_delete,
    )

    response = client.delete(
        f"/api/v1/athletes/{ATHLETE_ID}/passport",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 204
    assert captured["athlete_id"] == ATHLETE_ID
    assert captured["current_user_id"] == USER_ID
    assert passport_dependencies.committed is True


def test_non_owner_cannot_delete_passport(
    client: TestClient,
    passport_dependencies,
    monkeypatch,
) -> None:
    async def fake_delete(self, athlete_id, current_user_id):
        raise ForbiddenError(
            "You do not have permission to modify this athlete passport"
        )

    monkeypatch.setattr(
        AthletePassportService,
        "delete_passport",
        fake_delete,
    )

    response = client.delete(
        f"/api/v1/athletes/{ATHLETE_ID}/passport",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 403
    assert passport_dependencies.rolled_back is True
