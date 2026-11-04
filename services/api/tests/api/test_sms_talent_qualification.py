"""HTTP authorization tests for SMS Talent qualification."""

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.main import create_app
from app.repositories.talent_application_repository import TalentApplicationRepository
from app.services.talent_service import TalentService


USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()
APPLICATION_ID = uuid.uuid4()
URL = f"/api/v1/talent/applications/{APPLICATION_ID}/qualification"


@pytest.fixture
def talent_client(monkeypatch):
    app = create_app()

    async def fake_user():
        return SimpleNamespace(id=str(USER_ID))

    async def fake_session():
        yield object()

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db_session] = fake_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_unauthenticated_request_is_rejected():
    app = create_app()
    with TestClient(app) as client:
        response = client.get(URL)
    assert response.status_code in (401, 403)


def test_missing_application_returns_404(talent_client, monkeypatch):
    async def fake_get(self, application_id, **kwargs):
        return None

    monkeypatch.setattr(TalentApplicationRepository, "get_by_id", fake_get)

    response = talent_client.get(URL)
    assert response.status_code == 404


def test_other_user_cannot_access_application(talent_client, monkeypatch):
    async def fake_get(self, application_id, **kwargs):
        return SimpleNamespace(user_id=OTHER_USER_ID, status="completed")

    monkeypatch.setattr(TalentApplicationRepository, "get_by_id", fake_get)

    response = talent_client.get(URL)
    assert response.status_code == 403


def test_incomplete_evaluations_return_409(talent_client, monkeypatch):
    async def fake_get(self, application_id, **kwargs):
        return SimpleNamespace(user_id=USER_ID, status="submitted")

    monkeypatch.setattr(TalentApplicationRepository, "get_by_id", fake_get)

    response = talent_client.get(URL)
    assert response.status_code == 409


def test_owner_receives_qualification(talent_client, monkeypatch):
    async def fake_get(self, application_id, **kwargs):
        return SimpleNamespace(user_id=USER_ID, status="completed")

    async def fake_qualification(self, *, application_id):
        return "eligible_for_coaching"

    monkeypatch.setattr(TalentApplicationRepository, "get_by_id", fake_get)
    monkeypatch.setattr(
        TalentService,
        "get_qualification_status",
        fake_qualification,
    )

    response = talent_client.get(URL)

    assert response.status_code == 200
    assert response.json() == {
        "qualification_status": "eligible_for_coaching"
    }
