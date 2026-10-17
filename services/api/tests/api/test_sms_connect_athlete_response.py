"""Authenticated HTTP boundary; decisions remain private and independently committed."""

from unittest.mock import AsyncMock

import pytest

from app.api.dependencies.auth import get_current_user
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.services.sms_connect_service import SMSConnectService
from tests.api.test_sms_connect_phase2 import INTEREST_ID, NOW, USER_ID, make_interest

PATH = f"/api/v1/sms-connect/athlete/interests/{INTEREST_ID}/response"


@pytest.fixture
def dependencies(client):
    session = AsyncMock()

    async def auth():
        return AuthUser(id=str(USER_ID), email="private@example.com")

    async def db():
        yield session

    client.app.dependency_overrides[get_current_user] = auth
    client.app.dependency_overrides[get_db_session] = db
    yield session
    client.app.dependency_overrides.clear()


@pytest.mark.parametrize("decision", ["interested", "declined"])
def test_success_safe_response_and_commit(client, dependencies, monkeypatch, decision):
    async def respond(self, *, interest_id, athlete_user_id, data):
        assert interest_id == INTEREST_ID and athlete_user_id == USER_ID
        assert data.athlete_response == decision
        interest = make_interest()
        interest.athlete_response = decision
        interest.athlete_responded_at = NOW
        interest.email = "secret@example.com"
        interest.phone = "secret"
        interest.whatsapp = "secret"
        return interest

    monkeypatch.setattr(SMSConnectService, "respond_to_interest", respond)
    response = client.patch(PATH, json={"athlete_response": decision})
    assert response.status_code == 200
    payload = response.json()
    assert payload["athlete_response"] == decision
    assert payload["athlete_responded_at"] is not None
    assert payload["status"] == "delivered"
    assert not {"requester_user_id", "email", "phone", "whatsapp"} & payload.keys()
    assert "secret" not in response.text
    dependencies.commit.assert_awaited_once()


@pytest.mark.parametrize(
    "payload",
    [
        {"athlete_response": "pending"},
        {"athlete_response": "approved"},
        {},
        {"athlete_response": "interested", "status": "closed"},
        {"athlete_response": "declined", "requester_user_id": str(USER_ID)},
    ],
)
def test_invalid_decision_or_extra_fields(client, dependencies, payload):
    assert client.patch(PATH, json=payload).status_code == 422
    dependencies.commit.assert_not_awaited()


@pytest.mark.parametrize(
    "error,code", [(NotFoundError, 404), (ForbiddenError, 403), (ConflictError, 409)]
)
def test_domain_error_rolls_back(client, dependencies, monkeypatch, error, code):
    monkeypatch.setattr(
        SMSConnectService, "respond_to_interest", AsyncMock(side_effect=error("Denied"))
    )
    assert client.patch(PATH, json={"athlete_response": "declined"}).status_code == code
    dependencies.commit.assert_not_awaited()
    dependencies.rollback.assert_awaited_once()


def test_auth_required(client):
    assert client.patch(PATH, json={"athlete_response": "interested"}).status_code in (401, 403)
