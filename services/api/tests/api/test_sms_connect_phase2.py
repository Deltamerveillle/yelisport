"""HTTP boundary tests for SMS Connect phase 2."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.dependencies.auth import get_current_user
from app.core.exceptions import ForbiddenError
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.services.sms_connect_service import SMSConnectService


USER_ID = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)

ATHLETE_ID = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)

INTEREST_ID = uuid.UUID(
    "33333333-3333-3333-3333-333333333333"
)

EVENT_ID = uuid.UUID(
    "44444444-4444-4444-4444-444444444444"
)

NOW = datetime(
    2026,
    9,
    4,
    20,
    0,
    tzinfo=timezone.utc,
)


class FakeSession:
    pass


def make_interest(
    *,
    status="delivered",
):
    return SimpleNamespace(
        id=INTEREST_ID,
        athlete_id=ATHLETE_ID,
        requester_user_id=uuid.UUID(
            "99999999-9999-9999-9999-999999999999"
        ),
        requester_role="recruiter",
        interest_type="recruitment",
        organization_name="SMS Test Club",
        subject="Professional opportunity",
        message=(
            "We would like to discuss a professional "
            "sporting opportunity."
        ),
        status=status,
        reviewed_at=NOW,
        delivered_at=(
            NOW if status in {"delivered", "closed"} else None
        ),
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def sms_connect_phase2_dependencies(
    client,
):
    session = FakeSession()

    async def override_current_user():
        return AuthUser(
            id=str(USER_ID),
            email="admin@example.com",
        )

    async def override_db():
        yield session

    client.app.dependency_overrides[
        get_current_user
    ] = override_current_user

    client.app.dependency_overrides[
        get_db_session
    ] = override_db

    yield session

    client.app.dependency_overrides.clear()


def test_athlete_inbox_forwards_authenticated_user(
    client,
    sms_connect_phase2_dependencies,
    monkeypatch,
):
    captured = {}

    async def fake_inbox(
        self,
        athlete_user_id,
    ):
        captured["athlete_user_id"] = (
            athlete_user_id
        )
        return [
            make_interest()
        ]

    monkeypatch.setattr(
        SMSConnectService,
        "list_athlete_inbox",
        fake_inbox,
    )

    response = client.get(
        "/api/v1/sms-connect/athlete/inbox"
    )

    assert response.status_code == 200

    assert (
        captured["athlete_user_id"]
        == USER_ID
    )

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["status"] == "delivered"

    assert "requester_user_id" not in payload[0]
    assert "email" not in payload[0]
    assert "phone" not in payload[0]
    assert "whatsapp" not in payload[0]


def test_admin_queue_forwards_filters_and_identity(
    client,
    sms_connect_phase2_dependencies,
    monkeypatch,
):
    captured = {}

    async def fake_list(
        self,
        *,
        admin_user_id,
        interest_status=None,
        limit=100,
        offset=0,
    ):
        captured.update(
            {
                "admin_user_id": admin_user_id,
                "interest_status": interest_status,
                "limit": limit,
                "offset": offset,
            }
        )

        return [
            make_interest(
                status="submitted"
            )
        ]

    monkeypatch.setattr(
        SMSConnectService,
        "list_admin_interests",
        fake_list,
    )

    response = client.get(
        "/api/v1/sms-connect/admin/interests",
        params={
            "interest_status": "submitted",
            "limit": 20,
            "offset": 5,
        },
    )

    assert response.status_code == 200

    assert captured["admin_user_id"] == USER_ID
    assert (
        captured["interest_status"]
        == "submitted"
    )
    assert captured["limit"] == 20
    assert captured["offset"] == 5

    payload = response.json()[0]

    assert "requester_user_id" not in payload


def test_admin_status_transition_forwards_request(
    client,
    sms_connect_phase2_dependencies,
    monkeypatch,
):
    captured = {}

    async def fake_transition(
        self,
        *,
        interest_id,
        admin_user_id,
        data,
    ):
        captured["interest_id"] = interest_id
        captured["admin_user_id"] = (
            admin_user_id
        )
        captured["status"] = data.status
        captured["note"] = data.note

        return make_interest(
            status="under_review"
        )

    monkeypatch.setattr(
        SMSConnectService,
        "transition_interest",
        fake_transition,
    )

    response = client.patch(
        (
            "/api/v1/sms-connect/admin/"
            f"interests/{INTEREST_ID}/status"
        ),
        json={
            "status": "under_review",
            "note": "Verification started",
        },
    )

    assert response.status_code == 200

    assert (
        captured["interest_id"]
        == INTEREST_ID
    )
    assert (
        captured["admin_user_id"]
        == USER_ID
    )
    assert (
        captured["status"]
        == "under_review"
    )
    assert (
        captured["note"]
        == "Verification started"
    )

    payload = response.json()

    assert payload["status"] == "under_review"
    assert "requester_user_id" not in payload
    assert "email" not in payload
    assert "phone" not in payload
    assert "whatsapp" not in payload


def test_invalid_transition_status_is_rejected_by_http_schema(
    client,
    sms_connect_phase2_dependencies,
):
    response = client.patch(
        (
            "/api/v1/sms-connect/admin/"
            f"interests/{INTEREST_ID}/status"
        ),
        json={
            "status": "hacked_status",
        },
    )

    assert response.status_code == 422


def test_transition_rejects_unknown_extra_fields(
    client,
    sms_connect_phase2_dependencies,
):
    response = client.patch(
        (
            "/api/v1/sms-connect/admin/"
            f"interests/{INTEREST_ID}/status"
        ),
        json={
            "status": "under_review",
            "requester_user_id": str(USER_ID),
        },
    )

    assert response.status_code == 422


def test_admin_audit_history_hides_actor_user_id(
    client,
    sms_connect_phase2_dependencies,
    monkeypatch,
):
    async def fake_events(
        self,
        *,
        interest_id,
        admin_user_id,
    ):
        assert interest_id == INTEREST_ID
        assert admin_user_id == USER_ID

        return [
            SimpleNamespace(
                id=EVENT_ID,
                interest_id=INTEREST_ID,
                actor_user_id=USER_ID,
                actor_role="admin",
                from_status="submitted",
                to_status="under_review",
                note="Verification started",
                created_at=NOW,
            )
        ]

    monkeypatch.setattr(
        SMSConnectService,
        "list_interest_events",
        fake_events,
    )

    response = client.get(
        (
            "/api/v1/sms-connect/admin/"
            f"interests/{INTEREST_ID}/events"
        )
    )

    assert response.status_code == 200

    event = response.json()[0]

    assert event["actor_role"] == "admin"
    assert (
        event["from_status"]
        == "submitted"
    )
    assert (
        event["to_status"]
        == "under_review"
    )

    assert "actor_user_id" not in event


def test_non_admin_service_denial_becomes_forbidden(
    client,
    sms_connect_phase2_dependencies,
    monkeypatch,
):
    async def fake_list(
        self,
        **kwargs,
    ):
        raise ForbiddenError(
            "A verified SMS administrator role "
            "is required"
        )

    monkeypatch.setattr(
        SMSConnectService,
        "list_admin_interests",
        fake_list,
    )

    response = client.get(
        "/api/v1/sms-connect/admin/interests"
    )

    assert response.status_code == 403


def test_phase2_routes_require_authentication(
    client,
):
    client.app.dependency_overrides.clear()

    paths = [
        (
            "GET",
            "/api/v1/sms-connect/athlete/inbox",
        ),
        (
            "GET",
            "/api/v1/sms-connect/admin/interests",
        ),
        (
            "GET",
            (
                "/api/v1/sms-connect/admin/"
                f"interests/{INTEREST_ID}/events"
            ),
        ),
    ]

    for method, path in paths:
        response = client.request(
            method,
            path,
        )

        assert response.status_code in {
            401,
            403,
        }
