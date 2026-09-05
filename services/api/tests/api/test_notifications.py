"""HTTP tests for authenticated SMS notifications."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.services.notification_service import NotificationService


USER_ID = uuid.uuid4()
NOTIFICATION_ID = uuid.uuid4()
RESOURCE_ID = uuid.uuid4()


def make_notification(
    *,
    is_read=False,
):
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        id=NOTIFICATION_ID,
        recipient_user_id=USER_ID,
        notification_type=(
            "sms_connect_interest_delivered"
        ),
        title="Nouvel intérêt professionnel",
        body=(
            "SMS vous a transmis un nouvel intérêt "
            "professionnel de Africa Talent FC."
        ),
        source="sms",
        resource_type="sms_connect_interest",
        resource_id=RESOURCE_ID,
        dedupe_key=(
            f"sms_connect:{RESOURCE_ID}:delivered"
        ),
        is_read=is_read,
        read_at=now if is_read else None,
        created_at=now,
    )


@pytest.fixture
def notification_dependencies(client):
    async def fake_db():
        yield SimpleNamespace()

    async def fake_user():
        return AuthUser(
            id=str(USER_ID),
            email="athlete@example.com",
        )

    client.app.dependency_overrides[
        get_db_session
    ] = fake_db

    client.app.dependency_overrides[
        get_current_user
    ] = fake_user

    yield

    client.app.dependency_overrides.clear()


def test_list_my_notifications_returns_safe_response(
    client,
    notification_dependencies,
    monkeypatch,
):
    async def fake_list(
        self,
        user_id,
        *,
        unread_only,
        limit,
        offset,
    ):
        assert user_id == USER_ID
        assert unread_only is True
        assert limit == 25
        assert offset == 0
        return [make_notification()]

    monkeypatch.setattr(
        NotificationService,
        "list_my_notifications",
        fake_list,
    )

    response = client.get(
        "/api/v1/notifications/me"
        "?unread_only=true&limit=25"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["is_read"] is False
    assert (
        body[0]["notification_type"]
        == "sms_connect_interest_delivered"
    )

    assert "recipient_user_id" not in body[0]
    assert "dedupe_key" not in body[0]
    assert "email" not in body[0]
    assert "phone" not in body[0]
    assert "whatsapp" not in body[0]


def test_unread_count_returns_count(
    client,
    notification_dependencies,
    monkeypatch,
):
    async def fake_count(
        self,
        user_id,
    ):
        assert user_id == USER_ID
        return 3

    monkeypatch.setattr(
        NotificationService,
        "unread_count",
        fake_count,
    )

    response = client.get(
        "/api/v1/notifications/me/unread-count"
    )

    assert response.status_code == 200
    assert response.json() == {
        "unread_count": 3
    }


def test_mark_notification_read(
    client,
    notification_dependencies,
    monkeypatch,
):
    async def fake_mark(
        self,
        *,
        notification_id,
        user_id,
    ):
        assert notification_id == NOTIFICATION_ID
        assert user_id == USER_ID
        return make_notification(
            is_read=True
        )

    monkeypatch.setattr(
        NotificationService,
        "mark_read",
        fake_mark,
    )

    response = client.patch(
        (
            f"/api/v1/notifications/"
            f"{NOTIFICATION_ID}/read"
        )
    )

    assert response.status_code == 200

    body = response.json()

    assert body["is_read"] is True
    assert body["read_at"] is not None
    assert "recipient_user_id" not in body
    assert "dedupe_key" not in body


def test_notifications_require_authentication(
    client,
):
    client.app.dependency_overrides.pop(
        get_current_user,
        None,
    )

    response = client.get(
        "/api/v1/notifications/me"
    )

    assert response.status_code in {
        401,
        403,
    }
