import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.core.exceptions import ConflictError, ForbiddenError
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.services.athlete_country_eligibility_service import (
    AthleteCountryEligibilityService,
)


USER_ID = uuid.UUID("28bbf25e-8d42-4a0a-8bc8-0f41be0fc114")
ATHLETE_ID = uuid.UUID("f42cc315-a4b8-4da5-9f7b-c1094cae2658")
COUNTRY_ID = uuid.UUID("12d66c6f-f5c7-4f17-a42b-a7933572320d")
ELIGIBILITY_ID = uuid.UUID("7bcd0762-c379-48ce-9ff1-564752299bbb")


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def eligibility_object(
    *,
    eligibility_id: uuid.UUID = ELIGIBILITY_ID,
    athlete_id: uuid.UUID = ATHLETE_ID,
    country_id: uuid.UUID = COUNTRY_ID,
    is_primary: bool = True,
):
    now = datetime.now(UTC)

    return SimpleNamespace(
        id=eligibility_id,
        athlete_id=athlete_id,
        country_id=country_id,
        status="declared",
        is_primary=is_primary,
        declared_at=now,
        documented_at=None,
        verified_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def eligibility_dependencies(client: TestClient):
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


def test_owner_can_declare_country_eligibility(
    client: TestClient,
    eligibility_dependencies,
    monkeypatch,
) -> None:
    captured = {}

    async def fake_declare(
        self,
        athlete_id,
        data,
        current_user_id,
    ):
        captured["athlete_id"] = athlete_id
        captured["country_id"] = data.country_id
        captured["current_user_id"] = current_user_id

        return eligibility_object(
            athlete_id=athlete_id,
            country_id=data.country_id,
            is_primary=True,
        )

    monkeypatch.setattr(
        AthleteCountryEligibilityService,
        "declare_eligibility",
        fake_declare,
    )

    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/eligibilities",
        json={
            "country_id": str(COUNTRY_ID),
            "is_primary": False,
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 201
    assert response.json()["athlete_id"] == str(ATHLETE_ID)
    assert response.json()["country_id"] == str(COUNTRY_ID)
    assert response.json()["status"] == "declared"
    assert response.json()["is_primary"] is True

    assert captured["athlete_id"] == ATHLETE_ID
    assert captured["country_id"] == COUNTRY_ID
    assert captured["current_user_id"] == USER_ID

    assert eligibility_dependencies.committed is True


def test_duplicate_country_eligibility_returns_409(
    client: TestClient,
    eligibility_dependencies,
    monkeypatch,
) -> None:
    async def fake_declare(
        self,
        athlete_id,
        data,
        current_user_id,
    ):
        raise ConflictError(
            "Country eligibility already exists for this athlete"
        )

    monkeypatch.setattr(
        AthleteCountryEligibilityService,
        "declare_eligibility",
        fake_declare,
    )

    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/eligibilities",
        json={
            "country_id": str(COUNTRY_ID),
            "is_primary": False,
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 409
    assert eligibility_dependencies.rolled_back is True


def test_non_owner_cannot_declare_country_eligibility(
    client: TestClient,
    eligibility_dependencies,
    monkeypatch,
) -> None:
    async def fake_declare(
        self,
        athlete_id,
        data,
        current_user_id,
    ):
        raise ForbiddenError(
            "You do not have permission to modify this athlete"
        )

    monkeypatch.setattr(
        AthleteCountryEligibilityService,
        "declare_eligibility",
        fake_declare,
    )

    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/eligibilities",
        json={
            "country_id": str(COUNTRY_ID),
            "is_primary": False,
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 403
    assert eligibility_dependencies.rolled_back is True


def test_list_country_eligibilities(
    client: TestClient,
    eligibility_dependencies,
    monkeypatch,
) -> None:
    async def fake_list(self, athlete_id):
        assert athlete_id == ATHLETE_ID
        return [
            eligibility_object(
                athlete_id=athlete_id,
                is_primary=True,
            )
        ]

    monkeypatch.setattr(
        AthleteCountryEligibilityService,
        "list_eligibilities",
        fake_list,
    )

    response = client.get(
        f"/api/v1/athletes/{ATHLETE_ID}/eligibilities",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["athlete_id"] == str(ATHLETE_ID)
    assert response.json()[0]["country_id"] == str(COUNTRY_ID)
    assert response.json()[0]["is_primary"] is True


def test_country_eligibility_payload_forbids_extra_fields(
    client: TestClient,
    eligibility_dependencies,
) -> None:
    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/eligibilities",
        json={
            "country_id": str(COUNTRY_ID),
            "is_primary": False,
            "status": "verified",
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 422
    assert eligibility_dependencies.committed is False
