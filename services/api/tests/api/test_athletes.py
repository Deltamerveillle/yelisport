import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.services.athlete_service import AthleteService


USER_ID = uuid.UUID("28bbf25e-8d42-4a0a-8bc8-0f41be0fc114")
OTHER_USER_ID = uuid.UUID("a451c6f7-b023-4bef-a5a1-f84caa15a2ac")
ATHLETE_ID = uuid.UUID("f42cc315-a4b8-4da5-9f7b-c1094cae2658")
SPORT_ID = uuid.UUID("11b4fa1b-0217-4a82-ad73-9784b043eece")


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def athlete_object(
    *,
    athlete_id: uuid.UUID = ATHLETE_ID,
    user_id: uuid.UUID = USER_ID,
    sport_id: uuid.UUID = SPORT_ID,
    first_name: str = "Dramane",
    last_name: str = "Fofana",
):
    now = datetime.now(UTC)

    return SimpleNamespace(
        id=athlete_id,
        user_id=user_id,
        sport_id=sport_id,
        first_name=first_name,
        last_name=last_name,
        nationality="Ivoirienne",
        country="Côte d'Ivoire",
        residence_country_id=None,
        city="Abidjan",
        biography="Profil sportif SMS",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def athlete_dependencies(client: TestClient):
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


def test_create_athlete_owned_by_authenticated_user(
    client: TestClient,
    athlete_dependencies,
    monkeypatch,
) -> None:
    captured = {}

    async def fake_create(self, data, current_user_id):
        captured["current_user_id"] = current_user_id
        captured["sport_id"] = data.sport_id
        return athlete_object(user_id=current_user_id)

    monkeypatch.setattr(AthleteService, "create_athlete", fake_create)

    payload = {
        "sport_id": str(SPORT_ID),
        "first_name": "Dramane",
        "last_name": "Fofana",
        "nationality": "Ivoirienne",
        "country": "Côte d'Ivoire",
        "city": "Abidjan",
        "biography": "Profil sportif SMS",
    }

    response = client.post(
        "/api/v1/athletes",
        json=payload,
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == str(USER_ID)
    assert captured["current_user_id"] == USER_ID
    assert captured["sport_id"] == SPORT_ID
    assert athlete_dependencies.committed is True


def test_payload_cannot_choose_another_owner(
    client: TestClient,
    athlete_dependencies,
    monkeypatch,
) -> None:
    captured = {}

    async def fake_create(self, data, current_user_id):
        captured["current_user_id"] = current_user_id
        return athlete_object(user_id=current_user_id)

    monkeypatch.setattr(AthleteService, "create_athlete", fake_create)

    response = client.post(
        "/api/v1/athletes",
        json={
            "user_id": str(OTHER_USER_ID),
            "sport_id": str(SPORT_ID),
            "first_name": "Dramane",
            "last_name": "Fofana",
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 422
    assert "current_user_id" not in captured


def test_duplicate_athlete_returns_409(
    client: TestClient,
    athlete_dependencies,
    monkeypatch,
) -> None:
    async def fake_create(self, data, current_user_id):
        raise ConflictError("Athlete profile already exists for this sport")

    monkeypatch.setattr(AthleteService, "create_athlete", fake_create)

    response = client.post(
        "/api/v1/athletes",
        json={
            "sport_id": str(SPORT_ID),
            "first_name": "Dramane",
            "last_name": "Fofana",
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 409
    assert athlete_dependencies.rolled_back is True


def test_get_athlete(
    client: TestClient,
    athlete_dependencies,
    monkeypatch,
) -> None:
    async def fake_get(self, athlete_id):
        assert athlete_id == ATHLETE_ID
        return athlete_object()

    monkeypatch.setattr(AthleteService, "get_athlete", fake_get)

    response = client.get(
        f"/api/v1/athletes/{ATHLETE_ID}",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(ATHLETE_ID)


def test_list_athletes(
    client: TestClient,
    athlete_dependencies,
    monkeypatch,
) -> None:
    async def fake_list(self):
        return [athlete_object()]

    monkeypatch.setattr(AthleteService, "list_athletes", fake_list)

    response = client.get(
        "/api/v1/athletes",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == str(ATHLETE_ID)


def test_owner_can_update_athlete(
    client: TestClient,
    athlete_dependencies,
    monkeypatch,
) -> None:
    captured = {}

    async def fake_update(self, athlete_id, data, current_user_id):
        captured["athlete_id"] = athlete_id
        captured["current_user_id"] = current_user_id
        return athlete_object(first_name=data.first_name or "Dramane")

    monkeypatch.setattr(AthleteService, "update_athlete", fake_update)

    response = client.put(
        f"/api/v1/athletes/{ATHLETE_ID}",
        json={"first_name": "Delta"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json()["first_name"] == "Delta"
    assert captured["athlete_id"] == ATHLETE_ID
    assert captured["current_user_id"] == USER_ID
    assert athlete_dependencies.committed is True


def test_non_owner_cannot_update_athlete(
    client: TestClient,
    athlete_dependencies,
    monkeypatch,
) -> None:
    async def fake_update(self, athlete_id, data, current_user_id):
        raise ForbiddenError(
            "You do not have permission to modify this athlete"
        )

    monkeypatch.setattr(AthleteService, "update_athlete", fake_update)

    response = client.put(
        f"/api/v1/athletes/{ATHLETE_ID}",
        json={"first_name": "Interdit"},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 403
    assert athlete_dependencies.rolled_back is True


def test_owner_can_delete_athlete(
    client: TestClient,
    athlete_dependencies,
    monkeypatch,
) -> None:
    captured = {}

    async def fake_delete(self, athlete_id, current_user_id):
        captured["athlete_id"] = athlete_id
        captured["current_user_id"] = current_user_id
        return True

    monkeypatch.setattr(AthleteService, "delete_athlete", fake_delete)

    response = client.delete(
        f"/api/v1/athletes/{ATHLETE_ID}",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 204
    assert captured["athlete_id"] == ATHLETE_ID
    assert captured["current_user_id"] == USER_ID
    assert athlete_dependencies.committed is True


def test_nonexistent_athlete_returns_404(
    client: TestClient,
    athlete_dependencies,
    monkeypatch,
) -> None:
    async def fake_get(self, athlete_id):
        raise NotFoundError("Athlete not found")

    monkeypatch.setattr(AthleteService, "get_athlete", fake_get)

    response = client.get(
        f"/api/v1/athletes/{ATHLETE_ID}",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 404


def test_update_cannot_change_sport_id(
    client: TestClient,
    athlete_dependencies,
) -> None:
    response = client.put(
        f"/api/v1/athletes/{ATHLETE_ID}",
        json={
            "sport_id": str(uuid.uuid4()),
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 422


# ============================================================
# SMS Nations — normalized residence country
# ============================================================


class FakeAthleteRepository:
    def __init__(self, athlete=None):
        self.athlete = athlete
        self.created = None
        self.updated = None

    async def get_by_user_and_sport(self, user_id, sport_id):
        return None

    async def create(self, athlete):
        self.created = athlete
        return athlete

    async def get_by_id(self, athlete_id, *, for_update=False):
        return self.athlete

    async def update(self, athlete):
        self.updated = athlete
        return athlete


class FakeCountryRepository:
    def __init__(self, country):
        self.country = country
        self.requested_country_id = None

    async def get_by_id(self, country_id):
        self.requested_country_id = country_id
        return self.country


def test_service_create_accepts_active_residence_country() -> None:
    import asyncio

    from app.schemas.athlete import AthleteCreate

    country_id = uuid.uuid4()

    athlete_repository = FakeAthleteRepository()
    country_repository = FakeCountryRepository(
        SimpleNamespace(
            id=country_id,
            is_active=True,
        )
    )

    service = AthleteService(
        athlete_repository,
        country_repository,
    )

    data = AthleteCreate(
        sport_id=SPORT_ID,
        first_name="Dramane",
        last_name="Fofana",
        residence_country_id=country_id,
    )

    athlete = asyncio.run(
        service.create_athlete(
            data,
            USER_ID,
        )
    )

    assert athlete.residence_country_id == country_id
    assert country_repository.requested_country_id == country_id
    assert athlete_repository.created is athlete


def test_service_create_rejects_unknown_residence_country() -> None:
    import asyncio

    from app.schemas.athlete import AthleteCreate

    country_id = uuid.uuid4()

    service = AthleteService(
        FakeAthleteRepository(),
        FakeCountryRepository(None),
    )

    data = AthleteCreate(
        sport_id=SPORT_ID,
        first_name="Dramane",
        last_name="Fofana",
        residence_country_id=country_id,
    )

    with pytest.raises(
        NotFoundError,
        match="Residence country not found or inactive",
    ):
        asyncio.run(
            service.create_athlete(
                data,
                USER_ID,
            )
        )


def test_service_create_rejects_inactive_residence_country() -> None:
    import asyncio

    from app.schemas.athlete import AthleteCreate

    country_id = uuid.uuid4()

    service = AthleteService(
        FakeAthleteRepository(),
        FakeCountryRepository(
            SimpleNamespace(
                id=country_id,
                is_active=False,
            )
        ),
    )

    data = AthleteCreate(
        sport_id=SPORT_ID,
        first_name="Dramane",
        last_name="Fofana",
        residence_country_id=country_id,
    )

    with pytest.raises(
        NotFoundError,
        match="Residence country not found or inactive",
    ):
        asyncio.run(
            service.create_athlete(
                data,
                USER_ID,
            )
        )


def test_service_update_can_clear_residence_country() -> None:
    import asyncio

    from app.schemas.athlete import AthleteUpdate

    athlete = SimpleNamespace(
        id=ATHLETE_ID,
        user_id=USER_ID,
        sport_id=SPORT_ID,
        first_name="Dramane",
        last_name="Fofana",
        nationality="Ivoirienne",
        country="Côte d'Ivoire",
        residence_country_id=uuid.uuid4(),
        city="Abidjan",
        biography=None,
    )

    athlete_repository = FakeAthleteRepository(athlete)

    service = AthleteService(
        athlete_repository,
        FakeCountryRepository(None),
    )

    updated = asyncio.run(
        service.update_athlete(
            ATHLETE_ID,
            AthleteUpdate(residence_country_id=None),
            USER_ID,
        )
    )

    assert updated.residence_country_id is None
    assert athlete_repository.updated is athlete
