"""Authenticated owner-only pilot HTTP boundary."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.main import create_app


@pytest.fixture
def pilot_client():
    app = create_app()
    session = AsyncMock()
    owner = uuid.uuid4()

    async def db():
        yield session

    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=str(owner))
    app.dependency_overrides[get_settings] = lambda: Settings(app_env="test")
    with TestClient(app) as client:
        yield client, app, session, owner


def test_anonymous_rejected(pilot_client):
    client, app, session, _ = pilot_client
    del app.dependency_overrides[get_current_user]
    assert client.post("/api/v1/subscriptions/me/trial").status_code in {401, 403}
    session.execute.assert_not_called()


def test_uses_authenticated_owner_only(pilot_client):
    client, _, session, owner = pilot_client
    now = datetime.now(UTC)
    row = SimpleNamespace(
        id=uuid.uuid4(),
        plan_code="monthly",
        status="trialing",
        provider="internal_free_test_pilot",
        current_period_start=now,
        current_period_end=now + timedelta(days=7),
        created_at=now,
        updated_at=now,
    )
    with patch("app.api.v1.endpoints.subscriptions.FreeTestPilotService") as service:
        service.return_value.activate = AsyncMock(return_value=row)
        response = client.post(
            "/api/v1/subscriptions/me/trial",
            json={
                "user_id": str(uuid.uuid4()),
                "duration_days": 999,
                "amount": 0,
                "entitlements": {"priority_visibility": True},
            },
        )
        assert response.status_code == 200
        service.return_value.activate.assert_awaited_once_with(owner)
        assert response.json()["current_period_end"] == row.current_period_end.isoformat().replace(
            "+00:00", "Z"
        )
    session.commit.assert_awaited_once()


def test_production_enabled_still_refused(pilot_client):
    client, app, session, _ = pilot_client
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="production", sms_free_test_pilot_enabled=True
    )
    assert client.post("/api/v1/subscriptions/me/trial").status_code == 404
    session.execute.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_awaited_once()
