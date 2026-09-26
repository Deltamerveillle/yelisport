"""Opportunity HTTP privacy, auth and transaction boundaries."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.api.dependencies.auth import get_current_user
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.services.sms_connect_service import SMSConnectService
from tests.api.test_sms_connect_phase2 import NOW, USER_ID

OPPORTUNITY_ID = uuid.uuid4()
ADMIN_PATH = f"/api/v1/sms-connect/admin/opportunities/{OPPORTUNITY_ID}/status"


def payload():
    return dict(
        id=OPPORTUNITY_ID,
        interest_id=uuid.uuid4(),
        status="active",
        opened_at=NOW,
        closed_at=None,
        created_at=NOW,
        updated_at=NOW,
        organization_name="Club",
        requester_role="club",
        interest_type="trial",
        subject="Opportunity",
        message="SMS mediated opportunity",
        requester_user_id=uuid.uuid4(),
        athlete_user_id=uuid.uuid4(),
        email="secret@example.com",
        phone="secret",
        whatsapp="secret",
    )


@pytest.fixture
def dependencies(client):
    session = AsyncMock()

    async def auth():
        return AuthUser(id=str(USER_ID), email="test@example.com")

    async def db():
        yield session

    client.app.dependency_overrides[get_current_user] = auth
    client.app.dependency_overrides[get_db_session] = db
    yield session
    client.app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "path,method",
    [
        ("athlete/opportunities", "list_athlete_opportunities"),
        ("me/opportunities", "list_my_opportunities"),
    ],
)
def test_scoped_safe_reads(client, dependencies, monkeypatch, path, method):
    service = AsyncMock(return_value=[payload()])
    monkeypatch.setattr(SMSConnectService, method, service)
    response = client.get(f"/api/v1/sms-connect/{path}")
    assert response.status_code == 200
    service.assert_awaited_once_with(USER_ID)
    result = response.json()[0]
    assert (
        not {"requester_user_id", "athlete_user_id", "email", "phone", "whatsapp"} & result.keys()
    )
    assert "secret" not in response.text
    dependencies.commit.assert_not_awaited()


def test_admin_success_commit_and_safe_response(client, dependencies, monkeypatch):
    data = payload()
    data["status"] = "progressing"
    service = AsyncMock(return_value=data)
    monkeypatch.setattr(SMSConnectService, "transition_opportunity", service)
    response = client.patch(ADMIN_PATH, json={"status": "progressing"})
    assert response.status_code == 200 and response.json()["status"] == "progressing"
    assert "requester_user_id" not in response.json() and "secret" not in response.text
    assert service.await_args.kwargs["admin_user_id"] == USER_ID
    dependencies.commit.assert_awaited_once()
    dependencies.rollback.assert_not_awaited()


@pytest.mark.parametrize("status", ["active", "withdrawn", "delivered", "unknown"])
def test_admin_cannot_bypass_lifecycle_schema(client, dependencies, status):
    assert client.patch(ADMIN_PATH, json={"status": status}).status_code == 422
    dependencies.commit.assert_not_awaited()


@pytest.mark.parametrize(
    "error,code", [(ForbiddenError, 403), (ConflictError, 409), (NotFoundError, 404)]
)
def test_errors_rollback(client, dependencies, monkeypatch, error, code):
    monkeypatch.setattr(
        SMSConnectService, "transition_opportunity", AsyncMock(side_effect=error("Denied"))
    )
    assert client.patch(ADMIN_PATH, json={"status": "progressing"}).status_code == code
    dependencies.rollback.assert_awaited_once()
    dependencies.commit.assert_not_awaited()


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/sms-connect/athlete/opportunities"),
        ("GET", "/api/v1/sms-connect/me/opportunities"),
        ("PATCH", ADMIN_PATH),
    ],
)
def test_auth_required(client, method, path):
    assert client.request(method, path, json={"status": "progressing"}).status_code in (401, 403)
