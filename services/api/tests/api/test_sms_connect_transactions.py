"""Both historical write endpoints validate before commit and rollback every failure."""

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.api.dependencies.auth import get_current_user
from app.core.exceptions import ForbiddenError
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.services.sms_connect_service import SMSConnectService
from tests.api.test_sms_connect_phase2 import ATHLETE_ID, INTEREST_ID, USER_ID, make_interest


@pytest.fixture
def transaction_session(client):
    session = AsyncMock()

    async def auth():
        return AuthUser(id=str(USER_ID), email="test@example.com")

    async def db():
        yield session

    client.app.dependency_overrides[get_current_user] = auth
    client.app.dependency_overrides[get_db_session] = db
    yield session
    client.app.dependency_overrides.clear()


@pytest.mark.parametrize("operation", ["create", "transition"])
@pytest.mark.parametrize("failure", ["service", "response", "commit"])
def test_write_failure_rolls_back(client, transaction_session, monkeypatch, operation, failure):
    if operation == "create":
        method = "create_interest"
        http_method = "POST"
        path = f"/api/v1/sms-connect/athletes/{ATHLETE_ID}/interests"
        payload = dict(
            interest_type="trial",
            organization_name="Club",
            subject="Trial",
            message="Professional opportunity through SMS",
        )
    else:
        method = "transition_interest"
        http_method = "PATCH"
        path = f"/api/v1/sms-connect/admin/interests/{INTEREST_ID}/status"
        payload = {"status": "delivered"}
    service = AsyncMock(return_value=make_interest())
    if failure == "service":
        service.side_effect = ForbiddenError("Denied")
    elif failure == "response":
        service.return_value = object()
    else:
        transaction_session.commit.side_effect = RuntimeError("Commit failed")
    monkeypatch.setattr(SMSConnectService, method, service)

    if failure == "service":
        assert client.request(http_method, path, json=payload).status_code == 403
    else:
        with pytest.raises(ValidationError if failure == "response" else RuntimeError):
            client.request(http_method, path, json=payload)
    transaction_session.rollback.assert_awaited_once()
    if failure == "commit":
        transaction_session.commit.assert_awaited_once()
    else:
        transaction_session.commit.assert_not_awaited()
