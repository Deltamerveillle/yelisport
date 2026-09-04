"""API tests for SMS Connect."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.services.sms_connect_service import SMSConnectService


ATHLETE_ID = uuid.uuid4()
REQUESTER_ID = uuid.uuid4()
INTEREST_ID = uuid.uuid4()


def make_interest():
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        id=INTEREST_ID,
        athlete_id=ATHLETE_ID,
        requester_role="club",
        interest_type="trial",
        organization_name="Africa Talent FC",
        subject="Invitation à un essai",
        message=(
            "Nous souhaitons inviter cet athlète "
            "à un essai professionnel."
        ),
        status="submitted",
        reviewed_at=None,
        delivered_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sms_connect_dependencies(client):
    async def fake_db():
        yield SimpleNamespace()

    async def fake_user():
        return AuthUser(
            id=str(REQUESTER_ID),
            email="club@example.com",
        )

    client.app.dependency_overrides[
        get_db_session
    ] = fake_db

    client.app.dependency_overrides[
        get_current_user
    ] = fake_user

    yield

    client.app.dependency_overrides.clear()


def test_create_sms_connect_interest_returns_201(
    client,
    sms_connect_dependencies,
    monkeypatch,
):
    async def fake_create(
        self,
        *,
        athlete_id,
        requester_user_id,
        data,
    ):
        assert athlete_id == ATHLETE_ID
        assert requester_user_id == REQUESTER_ID
        assert data.interest_type == "trial"

        return make_interest()

    monkeypatch.setattr(
        SMSConnectService,
        "create_interest",
        fake_create,
    )

    response = client.post(
        (
            f"/api/v1/sms-connect/athletes/"
            f"{ATHLETE_ID}/interests"
        ),
        json={
            "interest_type": "trial",
            "organization_name": "Africa Talent FC",
            "subject": "Invitation à un essai",
            "message": (
                "Nous souhaitons inviter cet athlète "
                "à un essai professionnel."
            ),
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["athlete_id"] == str(ATHLETE_ID)
    assert body["requester_role"] == "club"
    assert body["status"] == "submitted"

    assert "email" not in body
    assert "phone" not in body
    assert "whatsapp" not in body
    assert "requester_user_id" not in body


def test_invalid_interest_type_returns_422(
    client,
    sms_connect_dependencies,
):
    response = client.post(
        (
            f"/api/v1/sms-connect/athletes/"
            f"{ATHLETE_ID}/interests"
        ),
        json={
            "interest_type": "spam",
            "organization_name": "Fake Club",
            "subject": "Contact",
            "message": (
                "Ceci est un message suffisamment long."
            ),
        },
    )

    assert response.status_code == 422


def test_sms_connect_requires_authentication(
    client,
):
    client.app.dependency_overrides.pop(
        get_current_user,
        None,
    )

    response = client.post(
        (
            f"/api/v1/sms-connect/athletes/"
            f"{ATHLETE_ID}/interests"
        ),
        json={
            "interest_type": "trial",
            "organization_name": "Africa Talent FC",
            "subject": "Essai",
            "message": (
                "Invitation officielle à un essai."
            ),
        },
    )

    assert response.status_code in {
        401,
        403,
    }


def test_list_my_interests_returns_safe_response(
    client,
    sms_connect_dependencies,
    monkeypatch,
):
    async def fake_list(
        self,
        requester_user_id,
    ):
        assert requester_user_id == REQUESTER_ID
        return [make_interest()]

    monkeypatch.setattr(
        SMSConnectService,
        "list_my_interests",
        fake_list,
    )

    response = client.get(
        "/api/v1/sms-connect/me/interests"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["status"] == "submitted"

    assert "email" not in body[0]
    assert "phone" not in body[0]
    assert "whatsapp" not in body[0]
    assert "requester_user_id" not in body[0]
