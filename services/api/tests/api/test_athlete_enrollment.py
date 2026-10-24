"""Athlete enrolment security regression tests."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session

USER = uuid.UUID("11111111-1111-1111-1111-111111111111")
ATHLETE = uuid.UUID("22222222-2222-2222-2222-222222222222")


def test_my_athletes_uses_authenticated_user(client):
    async def auth():
        return SimpleNamespace(id=str(USER))

    async def db():
        yield AsyncMock()

    client.app.dependency_overrides[get_current_user] = auth
    client.app.dependency_overrides[get_db_session] = db
    try:
        with patch("app.api.v1.endpoints.athletes.AthleteService") as cls:
            cls.return_value.list_user_athletes = AsyncMock(return_value=[])
            response = client.get("/api/v1/athletes/me")
        assert response.status_code == 200
        assert response.json() == []
        cls.return_value.list_user_athletes.assert_awaited_once_with(USER)
    finally:
        client.app.dependency_overrides.clear()


def test_athlete_media_denies_without_subscription(client):
    async def auth():
        return SimpleNamespace(id=str(USER))

    async def db():
        yield AsyncMock()

    client.app.dependency_overrides[get_current_user] = auth
    client.app.dependency_overrides[get_db_session] = db
    try:
        with (
            patch("app.api.v1.endpoints.athlete_media.AthleteRepository") as owners,
            patch("app.api.v1.endpoints.athlete_media.SubscriptionService") as access,
        ):
            owners.return_value.get_by_id = AsyncMock(
                return_value=SimpleNamespace(user_id=USER),
            )
            access.return_value.get_access = AsyncMock(
                return_value=SimpleNamespace(has_premium_access=False),
            )
            response = client.post(
                f"/api/v1/athletes/{ATHLETE}/media",
                json={
                    "storage_path": f"{USER}/{ATHLETE}/{uuid.uuid4()}.jpg",
                    "media_type": "photo",
                    "mime_type": "image/jpeg",
                },
            )
        assert response.status_code == 403
    finally:
        client.app.dependency_overrides.clear()


def test_athlete_media_rejects_overlong_video(client):
    async def auth():
        return SimpleNamespace(id=str(USER))

    async def db():
        yield AsyncMock()

    client.app.dependency_overrides[get_current_user] = auth
    client.app.dependency_overrides[get_db_session] = db
    try:
        response = client.post(
            f"/api/v1/athletes/{ATHLETE}/media",
            json={
                "storage_path": f"{USER}/{ATHLETE}/{uuid.uuid4()}.mp4",
                "media_type": "video",
                "mime_type": "video/mp4",
                "duration_seconds": 35,
            },
        )
        assert response.status_code == 422
    finally:
        client.app.dependency_overrides.clear()


def test_upload_intent_denies_inactive_subscription(client):
    """Even a logged-in owner cannot obtain signed upload access without a plan."""
    async def auth():
        return SimpleNamespace(id=str(USER))

    async def db():
        yield AsyncMock()

    client.app.dependency_overrides[get_current_user] = auth
    client.app.dependency_overrides[get_db_session] = db
    try:
        with (
            patch("app.api.v1.endpoints.athlete_media.AthleteRepository") as owners,
            patch("app.api.v1.endpoints.athlete_media.SubscriptionService") as subs,
        ):
            owners.return_value.get_by_id = AsyncMock(
                return_value=SimpleNamespace(user_id=USER),
            )
            subs.return_value.get_access = AsyncMock(
                return_value=SimpleNamespace(has_premium_access=False),
            )
            response = client.post(
                f"/api/v1/athletes/{ATHLETE}/media/upload-intent",
                json={"media_type": "video", "mime_type": "video/mp4"},
            )
        assert response.status_code == 403
        assert "token" not in response.text
    finally:
        client.app.dependency_overrides.clear()


def test_upload_intent_denies_other_athletes(client):
    """Owner checks run before any storage signing calls."""
    async def auth():
        return SimpleNamespace(id=str(USER))

    async def db():
        yield AsyncMock()

    client.app.dependency_overrides[get_current_user] = auth
    client.app.dependency_overrides[get_db_session] = db
    try:
        with patch("app.api.v1.endpoints.athlete_media.AthleteRepository") as owners:
            owners.return_value.get_by_id = AsyncMock(
                return_value=SimpleNamespace(user_id=uuid.uuid4()),
            )
            response = client.post(
                f"/api/v1/athletes/{ATHLETE}/media/upload-intent",
                json={"media_type": "photo", "mime_type": "image/png"},
            )
        assert response.status_code == 404
    finally:
        client.app.dependency_overrides.clear()
