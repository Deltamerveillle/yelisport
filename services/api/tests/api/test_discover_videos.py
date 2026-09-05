"""API tests for SMS Discover."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.api.dependencies.auth import get_current_user
from app.core.exceptions import ForbiddenError
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.services.discover_video_service import DiscoverVideoService


USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ATHLETE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
VIDEO_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


class FakeSession:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


def make_video(**overrides):
    now = datetime.now(UTC)

    values = {
        "id": VIDEO_ID,
        "athlete_id": ATHLETE_ID,
        "video_url": "https://example.com/video.mp4",
        "thumbnail_url": "https://example.com/thumb.jpg",
        "caption": "Young African talent",
        "duration_seconds": 20,
        "publication_status": "draft",
        "moderation_status": "pending",
        "visibility": "public",
        "is_active": True,
        "view_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)

    return SimpleNamespace(**values)


@pytest.fixture
def discover_dependencies(client):
    session = FakeSession()

    async def override_current_user():
        return AuthUser(
            id=str(USER_ID),
            email="athlete@example.com",
        )

    async def override_db():
        yield session

    client.app.dependency_overrides[get_current_user] = override_current_user
    client.app.dependency_overrides[get_db_session] = override_db

    yield session

    client.app.dependency_overrides.clear()


def test_create_discover_video_success(
    client,
    discover_dependencies,
    monkeypatch,
):
    async def fake_create(
        self,
        athlete_id,
        data,
        current_user_id,
    ):
        assert athlete_id == ATHLETE_ID
        assert current_user_id == USER_ID
        assert data.duration_seconds == 20
        return make_video()

    monkeypatch.setattr(
        DiscoverVideoService,
        "create_video",
        fake_create,
    )

    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/discover-videos",
        json={
            "video_url": "https://example.com/video.mp4",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "caption": "Young African talent",
            "duration_seconds": 20,
            "visibility": "public",
        },
    )

    assert response.status_code == 201
    assert response.json()["athlete_id"] == str(ATHLETE_ID)
    assert response.json()["publication_status"] == "draft"
    assert response.json()["moderation_status"] == "pending"
    assert discover_dependencies.committed is True


def test_create_rejects_duration_below_15(
    client,
    discover_dependencies,
):
    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/discover-videos",
        json={
            "video_url": "https://example.com/video.mp4",
            "duration_seconds": 14,
        },
    )

    assert response.status_code == 422


def test_create_rejects_duration_above_30(
    client,
    discover_dependencies,
):
    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/discover-videos",
        json={
            "video_url": "https://example.com/video.mp4",
            "duration_seconds": 31,
        },
    )

    assert response.status_code == 422


def test_create_rejects_server_managed_fields(
    client,
    discover_dependencies,
):
    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/discover-videos",
        json={
            "video_url": "https://example.com/video.mp4",
            "duration_seconds": 20,
            "publication_status": "published",
            "moderation_status": "approved",
            "view_count": 999999,
            "is_active": False,
        },
    )

    assert response.status_code == 422


def test_create_rejects_athlete_id_in_payload(
    client,
    discover_dependencies,
):
    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/discover-videos",
        json={
            "athlete_id": str(
                uuid.UUID(
                    "99999999-9999-9999-9999-999999999999"
                )
            ),
            "video_url": "https://example.com/video.mp4",
            "duration_seconds": 20,
        },
    )

    assert response.status_code == 422


def test_create_forbidden_for_non_owner(
    client,
    discover_dependencies,
    monkeypatch,
):
    async def fake_create(
        self,
        athlete_id,
        data,
        current_user_id,
    ):
        raise ForbiddenError(
            "You do not have permission to manage "
            "Discover videos for this athlete"
        )

    monkeypatch.setattr(
        DiscoverVideoService,
        "create_video",
        fake_create,
    )

    response = client.post(
        f"/api/v1/athletes/{ATHLETE_ID}/discover-videos",
        json={
            "video_url": "https://example.com/video.mp4",
            "duration_seconds": 20,
        },
    )

    assert response.status_code == 403
    assert discover_dependencies.rolled_back is True


def test_list_owned_athlete_videos(
    client,
    discover_dependencies,
    monkeypatch,
):
    async def fake_list(
        self,
        athlete_id,
        current_user_id,
    ):
        assert athlete_id == ATHLETE_ID
        assert current_user_id == USER_ID
        return [make_video()]

    monkeypatch.setattr(
        DiscoverVideoService,
        "list_athlete_videos",
        fake_list,
    )

    response = client.get(
        f"/api/v1/athletes/{ATHLETE_ID}/discover-videos"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == str(VIDEO_ID)


def test_get_owned_discover_video(
    client,
    discover_dependencies,
    monkeypatch,
):
    async def fake_get(
        self,
        athlete_id,
        video_id,
        current_user_id,
    ):
        assert athlete_id == ATHLETE_ID
        assert video_id == VIDEO_ID
        assert current_user_id == USER_ID
        return make_video()

    monkeypatch.setattr(
        DiscoverVideoService,
        "get_video",
        fake_get,
    )

    response = client.get(
        f"/api/v1/athletes/{ATHLETE_ID}/discover-videos/{VIDEO_ID}"
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(VIDEO_ID)


def test_update_discover_video_success(
    client,
    discover_dependencies,
    monkeypatch,
):
    async def fake_update(
        self,
        athlete_id,
        video_id,
        data,
        current_user_id,
    ):
        assert athlete_id == ATHLETE_ID
        assert video_id == VIDEO_ID
        assert current_user_id == USER_ID
        assert data.caption == "Updated caption"

        return make_video(
            caption="Updated caption",
            duration_seconds=25,
        )

    monkeypatch.setattr(
        DiscoverVideoService,
        "update_video",
        fake_update,
    )

    response = client.put(
        f"/api/v1/athletes/{ATHLETE_ID}/discover-videos/{VIDEO_ID}",
        json={
            "caption": "Updated caption",
            "duration_seconds": 25,
        },
    )

    assert response.status_code == 200
    assert response.json()["caption"] == "Updated caption"
    assert discover_dependencies.committed is True


@pytest.mark.parametrize(
    "payload",
    [
        {"video_url": None},
        {"duration_seconds": None},
        {"visibility": None},
    ],
)
def test_update_rejects_null_for_required_database_fields(
    client,
    discover_dependencies,
    payload,
):
    response = client.put(
        f"/api/v1/athletes/{ATHLETE_ID}/discover-videos/{VIDEO_ID}",
        json=payload,
    )

    assert response.status_code == 422


def test_update_rejects_moderation_and_system_fields(
    client,
    discover_dependencies,
):
    response = client.put(
        f"/api/v1/athletes/{ATHLETE_ID}/discover-videos/{VIDEO_ID}",
        json={
            "moderation_status": "approved",
            "publication_status": "published",
            "view_count": 5000,
            "is_active": False,
        },
    )

    assert response.status_code == 422


def test_delete_discover_video_success(
    client,
    discover_dependencies,
    monkeypatch,
):
    called = {"deleted": False}

    async def fake_delete(
        self,
        athlete_id,
        video_id,
        current_user_id,
    ):
        assert athlete_id == ATHLETE_ID
        assert video_id == VIDEO_ID
        assert current_user_id == USER_ID
        called["deleted"] = True

    monkeypatch.setattr(
        DiscoverVideoService,
        "delete_video",
        fake_delete,
    )

    response = client.delete(
        f"/api/v1/athletes/{ATHLETE_ID}/discover-videos/{VIDEO_ID}"
    )

    assert response.status_code == 204
    assert called["deleted"] is True
    assert discover_dependencies.committed is True


def test_public_discover_feed(
    client,
    discover_dependencies,
    monkeypatch,
):
    async def fake_public(
        self,
        limit=50,
        offset=0,
    ):
        assert limit == 20
        assert offset == 0

        return [
            make_video(
                publication_status="published",
                moderation_status="approved",
            )
        ]

    monkeypatch.setattr(
        DiscoverVideoService,
        "list_public_discover",
        fake_public,
    )

    response = client.get(
        "/api/v1/discover?limit=20&offset=0"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["publication_status"] == "published"
    assert response.json()[0]["moderation_status"] == "approved"


def test_public_discover_rejects_invalid_pagination(
    client,
    discover_dependencies,
):
    response = client.get(
        "/api/v1/discover?limit=101"
    )

    assert response.status_code == 422


def test_request_discover_publication(
    client,
    discover_dependencies,
    monkeypatch,
):
    async def fake_request(
        self,
        athlete_id,
        video_id,
        current_user_id,
    ):
        assert athlete_id == ATHLETE_ID
        assert video_id == VIDEO_ID

        item = make_video()
        item.publication_status = "published"
        item.moderation_status = "pending"
        return item

    monkeypatch.setattr(
        DiscoverVideoService,
        "request_publication",
        fake_request,
    )

    response = client.post(
        (
            f"/api/v1/athletes/{ATHLETE_ID}/"
            f"discover-videos/{VIDEO_ID}/publish"
        )
    )

    assert response.status_code == 200

    body = response.json()

    assert body["publication_status"] == "published"
    assert body["moderation_status"] == "pending"
