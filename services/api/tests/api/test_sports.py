import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_auth_service
from app.db.session import get_db_session
from app.schemas.auth import AuthUser


class FakeAuthService:
    def user_from_token(self, access_token: str) -> AuthUser:
        return AuthUser(id=str(uuid.uuid4()), email="member@yelisport.ci")


class FakeScalars:
    def all(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                id=uuid.UUID("11b4fa1b-0217-4a82-ad73-9784b043eece"),
                slug="football",
                name="Football",
                description="Football association",
                icon_url=None,
                is_active=True,
            )
        ]


class FakeSession:
    sport = SimpleNamespace(
        id=uuid.UUID("11b4fa1b-0217-4a82-ad73-9784b043eece"),
        slug="football",
        name="Football",
        description="Football association",
        icon_url=None,
        is_active=True,
    )

    async def scalars(self, statement: object) -> FakeScalars:
        return FakeScalars()

    async def scalar(self, statement: object) -> SimpleNamespace:
        return self.sport


async def fake_session():
    yield FakeSession()


def test_sports_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/sports").status_code == 403


def test_sports_returns_active_catalogue(client: TestClient) -> None:
    client.app.dependency_overrides[get_auth_service] = FakeAuthService
    client.app.dependency_overrides[get_db_session] = fake_session
    response = client.get(
        "/api/v1/sports", headers={"Authorization": "Bearer access-token"}
    )
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "11b4fa1b-0217-4a82-ad73-9784b043eece",
            "slug": "football",
            "name": "Football",
            "description": "Football association",
            "icon_url": None,
        }
    ]


def test_sports_accepts_a_search_query(client: TestClient) -> None:
    client.app.dependency_overrides[get_auth_service] = FakeAuthService
    client.app.dependency_overrides[get_db_session] = fake_session
    response = client.get(
        "/api/v1/sports?search=foot",
        headers={"Authorization": "Bearer access-token"},
    )
    assert response.status_code == 200
    assert response.json()[0]["slug"] == "football"


def test_sport_detail_returns_selected_sport(client: TestClient) -> None:
    client.app.dependency_overrides[get_auth_service] = FakeAuthService
    client.app.dependency_overrides[get_db_session] = fake_session
    response = client.get(
        "/api/v1/sports/football",
        headers={"Authorization": "Bearer access-token"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Football"
