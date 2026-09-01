"""API tests for authenticated SMS subscriptions."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.main import app


USER_ID = uuid.uuid4()


async def override_current_user():
    return SimpleNamespace(id=USER_ID)


async def override_db_session():
    yield AsyncMock()


app.dependency_overrides[get_current_user] = override_current_user
app.dependency_overrides[get_db_session] = override_db_session

client = TestClient(app)


def test_get_current_subscription_returns_none_when_absent() -> None:
    with patch(
        "app.api.v1.endpoints.subscriptions.SubscriptionService"
    ) as service_cls:
        service = service_cls.return_value
        service.get_current_subscription = AsyncMock(return_value=None)

        response = client.get("/api/v1/subscriptions/me")

    assert response.status_code == 200
    assert response.json() is None


def test_get_subscription_access_returns_free_when_absent() -> None:
    with patch(
        "app.api.v1.endpoints.subscriptions.SubscriptionService"
    ) as service_cls:
        service = service_cls.return_value
        service.get_current_subscription = AsyncMock(return_value=None)

        response = client.get("/api/v1/subscriptions/me/access")

    assert response.status_code == 200
    assert response.json() == {
        "has_premium_access": False,
        "plan_code": "free",
        "status": "inactive",
        "current_period_end": None,
    }


def test_get_current_active_subscription() -> None:
    now = datetime.now(UTC)

    subscription = SimpleNamespace(
        id=uuid.uuid4(),
        plan_code="premium",
        status="active",
        provider="provider-x",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        created_at=now,
        updated_at=now,
    )

    with patch(
        "app.api.v1.endpoints.subscriptions.SubscriptionService"
    ) as service_cls:
        service = service_cls.return_value
        service.get_current_subscription = AsyncMock(
            return_value=subscription
        )

        response = client.get("/api/v1/subscriptions/me")

    assert response.status_code == 200

    body = response.json()
    assert body["id"] == str(subscription.id)
    assert body["plan_code"] == "premium"
    assert body["status"] == "active"
    assert body["provider"] == "provider-x"
    assert "provider_customer_id" not in body
    assert "provider_subscription_id" not in body


def test_get_subscription_history() -> None:
    now = datetime.now(UTC)

    subscriptions = [
        SimpleNamespace(
            id=uuid.uuid4(),
            plan_code="premium",
            status="expired",
            provider="provider-x",
            current_period_start=now - timedelta(days=60),
            current_period_end=now - timedelta(days=30),
            created_at=now - timedelta(days=60),
            updated_at=now - timedelta(days=30),
        ),
        SimpleNamespace(
            id=uuid.uuid4(),
            plan_code="premium",
            status="active",
            provider="provider-x",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            created_at=now,
            updated_at=now,
        ),
    ]

    with patch(
        "app.api.v1.endpoints.subscriptions.SubscriptionService"
    ) as service_cls:
        service = service_cls.return_value
        service.list_user_subscriptions = AsyncMock(
            return_value=subscriptions
        )

        response = client.get("/api/v1/subscriptions/me/history")

    assert response.status_code == 200

    body = response.json()
    assert len(body) == 2
    assert body[0]["status"] == "expired"
    assert body[1]["status"] == "active"


def test_get_active_subscription_access() -> None:
    now = datetime.now(UTC)

    subscription = SimpleNamespace(
        plan_code="premium",
        status="active",
        current_period_end=now + timedelta(days=30),
    )

    with patch(
        "app.api.v1.endpoints.subscriptions.SubscriptionService"
    ) as service_cls:
        service = service_cls.return_value
        service.get_current_subscription = AsyncMock(
            return_value=subscription
        )
        service.has_premium_access = AsyncMock(return_value=True)

        response = client.get("/api/v1/subscriptions/me/access")

    assert response.status_code == 200

    body = response.json()
    assert body["has_premium_access"] is True
    assert body["plan_code"] == "premium"
    assert body["status"] == "active"
