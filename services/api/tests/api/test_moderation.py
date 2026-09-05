"""API tests for SMS moderation."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.services.moderation_service import ModerationService


USER_ID = uuid.uuid4()
TARGET_ID = uuid.uuid4()
REPORT_ID = uuid.uuid4()
EVENT_ID = uuid.uuid4()


def make_report(
    *,
    status="submitted",
):
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        id=REPORT_ID,
        reporter_user_id=USER_ID,
        resource_type="discover_video",
        resource_id=TARGET_ID,
        reason="inappropriate_content",
        details="Contenu à vérifier.",
        status=status,
        created_at=now,
        updated_at=now,
    )


def make_event():
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        id=EVENT_ID,
        report_id=REPORT_ID,
        actor_user_id=USER_ID,
        actor_role="admin",
        action="under_review",
        from_status="submitted",
        to_status="under_review",
        note="Analyse commencée.",
        created_at=now,
    )


@pytest.fixture
def moderation_dependencies(client):
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )

    async def fake_db():
        yield session

    async def fake_user():
        return AuthUser(
            id=str(USER_ID),
            email="user@example.com",
        )

    client.app.dependency_overrides[
        get_db_session
    ] = fake_db

    client.app.dependency_overrides[
        get_current_user
    ] = fake_user

    yield session

    client.app.dependency_overrides.clear()


def test_create_moderation_report_returns_201(
    client,
    moderation_dependencies,
    monkeypatch,
):
    async def fake_create(
        self,
        *,
        reporter_user_id,
        data,
    ):
        assert reporter_user_id == USER_ID
        assert data.resource_type == "discover_video"
        assert data.resource_id == TARGET_ID
        assert data.reason == "inappropriate_content"

        return make_report()

    monkeypatch.setattr(
        ModerationService,
        "create_report",
        fake_create,
    )

    response = client.post(
        "/api/v1/moderation/reports",
        json={
            "resource_type": "discover_video",
            "resource_id": str(TARGET_ID),
            "reason": "inappropriate_content",
            "details": "Contenu à vérifier.",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["id"] == str(REPORT_ID)
    assert body["resource_id"] == str(TARGET_ID)
    assert body["status"] == "submitted"

    assert "reporter_user_id" not in body
    assert "actor_user_id" not in body


def test_invalid_moderation_reason_returns_422(
    client,
    moderation_dependencies,
):
    response = client.post(
        "/api/v1/moderation/reports",
        json={
            "resource_type": "discover_video",
            "resource_id": str(TARGET_ID),
            "reason": "not_a_real_reason",
        },
    )

    assert response.status_code == 422


def test_moderation_requires_authentication(
    client,
):
    client.app.dependency_overrides.pop(
        get_current_user,
        None,
    )

    response = client.post(
        "/api/v1/moderation/reports",
        json={
            "resource_type": "discover_video",
            "resource_id": str(TARGET_ID),
            "reason": "spam",
        },
    )

    assert response.status_code in {
        401,
        403,
    }


def test_list_my_reports_returns_safe_response(
    client,
    moderation_dependencies,
    monkeypatch,
):
    async def fake_list(
        self,
        *,
        reporter_user_id,
        limit,
        offset,
    ):
        assert reporter_user_id == USER_ID
        assert limit == 50
        assert offset == 0

        return [make_report()]

    monkeypatch.setattr(
        ModerationService,
        "list_my_reports",
        fake_list,
    )

    response = client.get(
        "/api/v1/moderation/me/reports"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["status"] == "submitted"
    assert "reporter_user_id" not in body[0]


def test_admin_queue_returns_internal_reporter_id(
    client,
    moderation_dependencies,
    monkeypatch,
):
    async def fake_admin_list(
        self,
        *,
        admin_user_id,
        status,
        resource_type,
        limit,
        offset,
    ):
        assert admin_user_id == USER_ID
        assert status == "submitted"
        assert resource_type == "discover_video"

        return [make_report()]

    monkeypatch.setattr(
        ModerationService,
        "list_admin_reports",
        fake_admin_list,
    )

    response = client.get(
        (
            "/api/v1/moderation/admin/reports"
            "?status=submitted"
            "&resource_type=discover_video"
        )
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["reporter_user_id"] == str(USER_ID)


def test_admin_transition_report(
    client,
    moderation_dependencies,
    monkeypatch,
):
    async def fake_transition(
        self,
        *,
        report_id,
        admin_user_id,
        data,
    ):
        assert report_id == REPORT_ID
        assert admin_user_id == USER_ID
        assert data.status == "under_review"

        return make_report(
            status="under_review"
        )

    monkeypatch.setattr(
        ModerationService,
        "transition_report",
        fake_transition,
    )

    response = client.patch(
        (
            f"/api/v1/moderation/admin/reports/"
            f"{REPORT_ID}/status"
        ),
        json={
            "status": "under_review",
            "note": "Analyse commencée.",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "under_review"
    assert body["reporter_user_id"] == str(USER_ID)


def test_invalid_admin_transition_payload_returns_422(
    client,
    moderation_dependencies,
):
    response = client.patch(
        (
            f"/api/v1/moderation/admin/reports/"
            f"{REPORT_ID}/status"
        ),
        json={
            "status": "submitted",
        },
    )

    assert response.status_code == 422


def test_admin_audit_response_hides_actor_user_id(
    client,
    moderation_dependencies,
    monkeypatch,
):
    async def fake_events(
        self,
        *,
        report_id,
        admin_user_id,
    ):
        assert report_id == REPORT_ID
        assert admin_user_id == USER_ID

        return [make_event()]

    monkeypatch.setattr(
        ModerationService,
        "list_report_events",
        fake_events,
    )

    response = client.get(
        (
            f"/api/v1/moderation/admin/reports/"
            f"{REPORT_ID}/events"
        )
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["action"] == "under_review"
    assert body[0]["actor_role"] == "admin"

    assert "actor_user_id" not in body[0]



def test_admin_can_approve_discover_video(
    client,
    moderation_dependencies,
    monkeypatch,
):
    async def fake_decide(
        self,
        *,
        report_id,
        admin_user_id,
        data,
    ):
        assert report_id == REPORT_ID
        assert admin_user_id == USER_ID
        assert data.decision == "approved"

        now = datetime.now(timezone.utc)

        return SimpleNamespace(
            id=TARGET_ID,
            athlete_id=uuid.uuid4(),
            video_url="https://example.com/video.mp4",
            thumbnail_url=None,
            caption="Talent",
            duration_seconds=20,
            publication_status="published",
            moderation_status="approved",
            visibility="public",
            is_active=True,
            view_count=0,
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(
        ModerationService,
        "decide_discover_video",
        fake_decide,
    )

    response = client.patch(
        (
            f"/api/v1/moderation/admin/reports/"
            f"{REPORT_ID}/discover-decision"
        ),
        json={
            "decision": "approved",
            "note": "Vidéo validée.",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["moderation_status"] == "approved"
    assert body["publication_status"] == "published"


def test_invalid_discover_decision_returns_422(
    client,
    moderation_dependencies,
):
    response = client.patch(
        (
            f"/api/v1/moderation/admin/reports/"
            f"{REPORT_ID}/discover-decision"
        ),
        json={
            "decision": "maybe",
        },
    )

    assert response.status_code == 422



def test_admin_can_suspend_user(
    client,
    moderation_dependencies,
    monkeypatch,
):
    async def fake_action(
        self,
        *,
        report_id,
        admin_user_id,
        data,
    ):
        assert report_id == REPORT_ID
        assert admin_user_id == USER_ID
        assert data.action == "suspend"

        return SimpleNamespace(
            id=TARGET_ID,
            is_active=False,
        )

    monkeypatch.setattr(
        ModerationService,
        "moderate_user",
        fake_action,
    )

    response = client.patch(
        (
            f"/api/v1/moderation/admin/reports/"
            f"{REPORT_ID}/user-action"
        ),
        json={
            "action": "suspend",
            "note": "Suspension validée.",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == str(TARGET_ID)
    assert body["is_active"] is False
    assert "email" not in body


def test_invalid_user_moderation_action_returns_422(
    client,
    moderation_dependencies,
):
    response = client.patch(
        (
            f"/api/v1/moderation/admin/reports/"
            f"{REPORT_ID}/user-action"
        ),
        json={
            "action": "ban_forever",
        },
    )

    assert response.status_code == 422
