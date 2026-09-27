"""Explicit commercial policy and legacy premium/consent separation."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.dependencies.auth import get_current_user
from app.core.config import Settings
from app.db.session import get_db_session
from app.main import create_app
from app.schemas.entitlements import CommercialEntitlements
from app.schemas.payment import PaymentInitiationRequest
from app.services import subscription_service as module
from app.services.subscription_service import SubscriptionService
from app.services.talent_service import TalentService
from tests.api.test_payments import plan

FLAGS = dict(
    talent_access=True,
    enhanced_profile=True,
    discover_visibility=True,
    connect_access=False,
    statistics_insights=True,
    priority_visibility=False,
)


def subscription(**changes):
    return SimpleNamespace(
        **(
            dict(
                status="active",
                plan_code="test_offer_v1",
                current_period_end=datetime.now(UTC) + timedelta(days=30),
                provider_customer_id="secret-customer",
                provider_subscription_id="secret-subscription",
                user_id=uuid.uuid4(),
            )
            | changes
        )
    )


def service_for(monkeypatch, row, plans):
    monkeypatch.setattr(module, "get_settings", lambda: Settings(sms_commercial_plans=plans))
    session = AsyncMock()
    service = SubscriptionService(session)
    service.subscriptions.get_current_for_user = AsyncMock(return_value=row)
    return service, session


@pytest.mark.parametrize("status", ["active", "trialing"])
async def test_configured_entitlements_exact_and_single_subscription_read(monkeypatch, status):
    row = subscription(status=status)
    service, session = service_for(monkeypatch, row, [plan(entitlements=FLAGS)])
    user_id = uuid.uuid4()
    result = await service.get_access(user_id)
    assert result.entitlements.model_dump() == FLAGS
    assert result.has_premium_access is True
    service.subscriptions.get_current_for_user.assert_awaited_once_with(user_id)
    assert session.mock_calls == []  # Resolution has no mutation/commit side effects.
    assert (
        not {"user_id", "provider_customer_id", "provider_subscription_id"}
        & result.model_dump().keys()
    )


@pytest.mark.parametrize(
    "state", ["none", "expired", "inactive", "cancelled", "free", "unknown", "omitted"]
)
async def test_fail_closed_without_changing_legacy_access(monkeypatch, state):
    row = subscription()
    plans = [plan(entitlements=FLAGS)]
    expected_premium = False
    if state == "none":
        row = None
    elif state == "expired":
        row.current_period_end = datetime.now(UTC) - timedelta(seconds=1)
    elif state in {"inactive", "cancelled"}:
        row.status = state
    elif state == "free":
        row.plan_code = "free"
    elif state == "unknown":
        row.plan_code = "legacy_paid"
        expected_premium = True
    else:
        plans = [plan()]
        expected_premium = True
    service, _ = service_for(monkeypatch, row, plans)
    result = await service.get_access(uuid.uuid4())
    assert result.entitlements == CommercialEntitlements()
    assert result.has_premium_access is expected_premium
    assert await service.has_premium_access(uuid.uuid4()) is expected_premium


async def test_empty_catalogue_and_no_end_date_preserve_legacy_premium(monkeypatch):
    service, _ = service_for(monkeypatch, subscription(current_period_end=None), [])
    result = await service.get_access(uuid.uuid4())
    assert result.has_premium_access and result.entitlements == CommercialEntitlements()


async def test_sales_availability_does_not_revoke_configured_subscription(monkeypatch):
    service, _ = service_for(
        monkeypatch,
        subscription(),
        [
            plan(active=False, purchasable=False, entitlements=FLAGS),
        ],
    )
    assert (await service.get_access(uuid.uuid4())).entitlements.model_dump() == FLAGS


async def test_partial_configuration_only_grants_explicit_fields(monkeypatch):
    service, _ = service_for(
        monkeypatch,
        subscription(),
        [
            plan(entitlements={"enhanced_profile": True}),
        ],
    )
    expected = CommercialEntitlements(enhanced_profile=True)
    assert (await service.get_access(uuid.uuid4())).entitlements == expected


@pytest.mark.parametrize("field", list(FLAGS))
@pytest.mark.parametrize("value", [1, "true", None])
def test_strict_configuration_rejects_non_boolean_flags(field, value):
    with pytest.raises(ValidationError):
        plan(entitlements={field: value})


def test_unknown_entitlement_and_frozen_model():
    with pytest.raises(ValidationError):
        plan(entitlements={"sporting_score_boost": True})
    with pytest.raises(ValidationError):
        CommercialEntitlements().connect_access = True


@pytest.mark.parametrize("field", ["entitlements", *FLAGS])
def test_purchase_request_cannot_grant_entitlements(field):
    with pytest.raises(ValidationError):
        PaymentInitiationRequest.model_validate({"plan_code": "test_offer_v1", field: True})


async def test_talent_keeps_legacy_access_without_inferring_opportunity_consent(monkeypatch):
    subscription_service, _ = service_for(monkeypatch, subscription(plan_code="legacy_paid"), [])
    assert (await subscription_service.get_access(uuid.uuid4())).entitlements.talent_access is False
    service = TalentService(AsyncMock())
    service.subscription_service = subscription_service
    user_id, athlete_id = uuid.uuid4(), uuid.uuid4()
    athlete = SimpleNamespace(id=athlete_id, user_id=user_id, sport_id=uuid.uuid4())
    service.athletes.get_by_id = AsyncMock(return_value=athlete)
    service.applications.get_open_for_athlete = AsyncMock(return_value=None)
    service.applications.create = AsyncMock(side_effect=lambda application: application)
    result = await service.create_application(athlete_id=athlete_id, user_id=user_id)
    assert result.status == "draft"
    assert not hasattr(athlete, "available_for_opportunities")


@pytest.fixture
def api(monkeypatch):
    service, session = service_for(monkeypatch, subscription(), [plan(entitlements=FLAGS)])
    # Exercise the real endpoint and real resolver, replacing database I/O only.
    monkeypatch.setattr(
        module.SubscriptionRepository,
        "get_current_for_user",
        service.subscriptions.get_current_for_user,
    )
    app = create_app()

    async def db():
        yield session

    app.dependency_overrides[get_db_session] = db
    with TestClient(app) as client:
        yield app, client, session


def test_access_auth_and_owner_safe_real_resolution(api):
    app, client, session = api
    assert client.get("/api/v1/subscriptions/me/access").status_code in (401, 403)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=str(uuid.uuid4()))
    response = client.get("/api/v1/subscriptions/me/access")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "has_premium_access",
        "plan_code",
        "status",
        "current_period_end",
        "entitlements",
    }
    assert body["entitlements"] == FLAGS
    assert "secret" not in response.text
    session.commit.assert_not_awaited()
    session.flush.assert_not_awaited()
    # No client route can edit access; query arguments cannot override configuration.
    assert (
        client.patch("/api/v1/subscriptions/me/access", json={"entitlements": FLAGS}).status_code
        == 405
    )
    result = client.get("/api/v1/subscriptions/me/access?connect_access=true")
    assert result.json()["entitlements"]["connect_access"] is False
    result = client.post(
        "/api/v1/payments/initiate",
        json={
            "plan_code": "test_offer_v1",
            "entitlements": FLAGS,
        },
    )
    assert result.status_code == 422
