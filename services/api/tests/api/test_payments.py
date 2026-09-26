"""Catalogue, transaction boundaries and client trust restrictions."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.dependencies.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db_session
from app.main import create_app
from app.schemas.payment import CommercialPlan
from app.services.payment_initiation_service import PaymentInitiationService


def plan(**changes):
    return CommercialPlan(
        **(
            dict(
                plan_code="test_offer_v1",
                name="Test only",
                description="Not a commercial tariff",
                amount_minor=1234,
                currency="XOF",
                duration_days=30,
                active=True,
                purchasable=True,
            )
            | changes
        )
    )


@pytest.fixture
def context():
    app = create_app()
    session = AsyncMock()
    user_id = uuid.uuid4()
    settings = Settings(sms_commercial_plans=[plan(), plan(plan_code="disabled", active=False)])

    async def db():
        yield session

    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=str(user_id))
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, session, user_id, app


def payment():
    return SimpleNamespace(
        id=uuid.uuid4(),
        reference="SMS-random",
        plan_code="test_offer_v1",
        amount_minor=1234,
        currency="XOF",
        status="pending",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        user_id=uuid.uuid4(),
        provider_transaction_id="private",
        provider_customer_id="private",
    )


def test_catalogue_public_and_only_buyable(context):
    client, _, _, app = context
    del app.dependency_overrides[get_current_user]
    result = client.get("/api/v1/payments/plans")
    assert result.status_code == 200
    assert [p["plan_code"] for p in result.json()] == ["test_offer_v1"]
    assert result.json()[0]["duration_days"] == 30
    assert Settings(_env_file=None).sms_commercial_plans == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("amount_minor", 1),
        ("currency", "USD"),
        ("user_id", "other"),
        ("provider", "fake"),
        ("status", "succeeded"),
        ("duration_days", 999),
    ],
)
def test_client_cannot_set_commercial_or_internal_fields(context, field, value):
    client, session, _, _ = context
    response = client.post(
        "/api/v1/payments/initiate",
        json={
            "plan_code": "test_offer_v1",
            field: value,
        },
    )
    assert response.status_code == 422
    session.commit.assert_not_awaited()


def test_auth_required(context):
    client, _, _, app = context
    del app.dependency_overrides[get_current_user]
    assert client.post(
        "/api/v1/payments/initiate", json={"plan_code": "test_offer_v1"}
    ).status_code in (401, 403)
    assert client.get(f"/api/v1/payments/{uuid.uuid4()}").status_code in (401, 403)


def test_initiation_commits_validated_safe_response(context):
    client, session, user_id, _ = context
    with patch("app.api.v1.endpoints.payments.PaymentInitiationService") as cls:
        cls.return_value.initiate = AsyncMock(return_value=payment())
        result = client.post("/api/v1/payments/initiate", json={"plan_code": "test_offer_v1"})
        cls.return_value.initiate.assert_awaited_once_with(
            user_id=user_id,
            plan_code="test_offer_v1",
        )
    assert result.status_code == 200
    assert not {"user_id", "provider_transaction_id", "provider_customer_id"} & result.json().keys()
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.parametrize("failure", ["service", "response", "commit"])
def test_rollback_on_any_failure(context, failure):
    client, session, _, _ = context
    with patch("app.api.v1.endpoints.payments.PaymentInitiationService") as cls:
        cls.return_value.initiate = AsyncMock(return_value=payment())
        if failure == "service":
            cls.return_value.initiate.side_effect = ConflictError("unavailable")
        elif failure == "response":
            cls.return_value.initiate.return_value = None
        else:
            session.commit.side_effect = RuntimeError("commit failure")
        result = client.post("/api/v1/payments/initiate", json={"plan_code": "test_offer_v1"})
    assert result.status_code in (409, 500)
    session.rollback.assert_awaited_once()
    if failure != "commit":
        session.commit.assert_not_awaited()


@pytest.mark.parametrize("path", ["confirm", "succeeded", "verify"])
def test_no_client_confirmation_route(context, path):
    assert context[0].post(f"/api/v1/payments/{path}", json={}).status_code in (404, 405)


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_minor": True},
        {"amount_minor": 0},
        {"currency": "usd"},
        {"duration_days": 0},
        {"plan_code": "free"},
        {"name": " "},
    ],
)
def test_invalid_server_configuration_fails_closed(changes):
    with pytest.raises(ValidationError):
        plan(**changes)


def test_duplicate_plan_configuration_rejected():
    with pytest.raises(ValidationError):
        Settings(sms_commercial_plans=[plan(), plan()])


@pytest.mark.parametrize("code,error", [("unknown", NotFoundError), ("off", ConflictError)])
async def test_unavailable_plan_does_not_access_database(code, error):
    session = AsyncMock()
    service = PaymentInitiationService(session, [plan(plan_code="off", purchasable=False)])
    with pytest.raises(error):
        await service.initiate(user_id=uuid.uuid4(), plan_code=code)
    session.execute.assert_not_awaited()


async def test_owner_read_protection():
    service = PaymentInitiationService(AsyncMock(), [])
    row = payment()
    service.payments.get_by_id = AsyncMock(return_value=row)
    with pytest.raises(NotFoundError):
        await service.get_owned(user_id=uuid.uuid4(), transaction_id=row.id)
    assert await service.get_owned(user_id=row.user_id, transaction_id=row.id) is row


def test_owner_http_response_and_foreign_not_found(context):
    client, _, user_id, _ = context
    row = payment()
    with patch("app.api.v1.endpoints.payments.PaymentInitiationService") as cls:
        cls.return_value.get_owned = AsyncMock(return_value=row)
        response = client.get(f"/api/v1/payments/{row.id}")
        cls.return_value.get_owned.assert_awaited_once_with(
            user_id=user_id,
            transaction_id=row.id,
        )
        assert response.status_code == 200
        assert "user_id" not in response.json()
        cls.return_value.get_owned.side_effect = NotFoundError("Paiement introuvable")
        assert client.get(f"/api/v1/payments/{row.id}").status_code == 404
