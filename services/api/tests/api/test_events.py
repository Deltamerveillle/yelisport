import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_auth_service
from app.api.v1.endpoints.events import get_event_service
from app.models.event import RegistrationStatus
from app.schemas.auth import AuthUser

USER_ID = "28bbf25e-8d42-4a0a-8bc8-0f41be0fc114"
EVENT_ID = uuid.UUID("5ac8dcd6-1278-4fa9-b285-e7e07149b3b4")
SPORT_ID = uuid.UUID("11b4fa1b-0217-4a82-ad73-9784b043eece")


class FakeAuthService:
    def user_from_token(self, access_token: str) -> AuthUser:
        return AuthUser(id=USER_ID, email="member@yelisport.ci")


class FakeEventService:
    event = SimpleNamespace(
        id=EVENT_ID,
        sport_id=SPORT_ID,
        organizer_id=uuid.UUID(USER_ID),
        title="Football du samedi",
        description="Match amical",
        location="Abidjan",
        starts_at=datetime.now(UTC) + timedelta(days=2),
        ends_at=datetime.now(UTC) + timedelta(days=2, hours=2),
        capacity=20,
    )

    async def create(self, payload: object, organizer_id: uuid.UUID) -> SimpleNamespace:
        return self.event

    async def list_upcoming(self) -> list[SimpleNamespace]:
        return [self.event]

    async def list_mine(self, user_id: uuid.UUID) -> list[SimpleNamespace]:
        return [self.event]

    async def register(self, event_id: uuid.UUID, user_id: uuid.UUID) -> SimpleNamespace:
        return SimpleNamespace(event_id=event_id, status=RegistrationStatus.REGISTERED)

    async def cancel(self, event_id: uuid.UUID, user_id: uuid.UUID) -> SimpleNamespace:
        return SimpleNamespace(event_id=event_id, status=RegistrationStatus.CANCELLED)


def override_dependencies(client: TestClient) -> None:
    client.app.dependency_overrides[get_auth_service] = FakeAuthService
    client.app.dependency_overrides[get_event_service] = FakeEventService


def test_create_event(client: TestClient) -> None:
    override_dependencies(client)
    start = datetime.now(UTC) + timedelta(days=2)
    response = client.post(
        "/api/v1/events",
        headers={"Authorization": "Bearer token"},
        json={
            "sport_id": str(SPORT_ID),
            "title": "Football du samedi",
            "description": "Match amical",
            "location": "Abidjan",
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=2)).isoformat(),
            "capacity": 20,
        },
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Football du samedi"


def test_list_and_register_for_events(client: TestClient) -> None:
    override_dependencies(client)
    headers = {"Authorization": "Bearer token"}
    assert client.get("/api/v1/events", headers=headers).status_code == 200
    response = client.post(f"/api/v1/events/{EVENT_ID}/registrations", headers=headers)
    assert response.json()["status"] == "registered"


def test_list_mine_and_cancel_registration(client: TestClient) -> None:
    override_dependencies(client)
    headers = {"Authorization": "Bearer token"}
    mine = client.get("/api/v1/events/mine", headers=headers)
    assert mine.status_code == 200
    assert mine.json()[0]["id"] == str(EVENT_ID)
    cancelled = client.delete(f"/api/v1/events/{EVENT_ID}/registrations/me", headers=headers)
    assert cancelled.json()["status"] == "cancelled"
