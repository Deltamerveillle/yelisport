"""Pilot persistence and concurrency on disposable PostgreSQL schemas."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.subscriptions import activate_my_trial
from app.core.config import Settings
from app.core.exceptions import ConflictError
from app.models.payment_transaction import PaymentTransaction
from app.models.subscription import Subscription
from app.models.user import User
from app.services.free_test_pilot_service import TRIAL_PROVIDER, FreeTestPilotService
from app.services.subscription_service import SubscriptionService
from tests import test_payment_initiation_postgres as foundation
from tests.api.test_payments import plan
from tests.test_payment_initiation_postgres import count

database = foundation.database


@pytest.fixture
def settings():
    return Settings(
        sms_free_test_pilot_enabled=True,
        sms_free_test_pilot_plan_code="monthly",
        sms_free_test_pilot_duration_days=3,
        sms_commercial_plans=[
            plan(
                plan_code="monthly",
                entitlements={
                    "talent_access": True,
                    "enhanced_profile": True,
                    "discover_visibility": True,
                    "connect_access": True,
                    "statistics_insights": True,
                },
            )
        ],
    )


async def activate(engine, user_id, settings):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        return await activate_my_trial(SimpleNamespace(id=str(user_id)), session, settings)


async def test_activation_entitlements_retry_and_isolation(database, settings):
    engine, user_id = database
    a, b = await asyncio.wait_for(
        asyncio.gather(activate(engine, user_id, settings), activate(engine, user_id, settings)),
        timeout=10,
    )
    assert a.id == b.id and a.current_period_end == b.current_period_end
    assert a.status == "trialing" and a.provider == TRIAL_PROVIDER
    assert a.current_period_start.utcoffset() is not None
    assert a.current_period_end - a.current_period_start == timedelta(days=3)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        assert await count(session, Subscription) == 1
        assert await count(session, PaymentTransaction) == 0
        other = uuid.uuid4()
        session.add(User(id=other, email="trial-other@example.test"))
        await session.commit()
        with patch("app.services.subscription_service.get_settings", return_value=settings):
            access = await SubscriptionService(session).get_access(user_id)
            assert access.entitlements == settings.sms_commercial_plans[0].entitlements
            assert access.has_premium_access and not access.entitlements.priority_visibility
            assert not (await SubscriptionService(session).get_access(other)).has_premium_access
    other_trial = await activate(engine, other, settings)
    assert other_trial.id != a.id


@pytest.mark.parametrize("status", ["trialing", "expired", "replaced", "cancelled"])
async def test_persistent_consumption_and_expiration(database, settings, status):
    engine, user_id = database
    trial = await activate(engine, user_id, settings)
    async with AsyncSession(engine) as session:
        row = await session.get(Subscription, trial.id)
        row.status = status
        row.current_period_end = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    async with AsyncSession(engine) as session:
        access = await SubscriptionService(session).get_access(user_id)
        assert not access.has_premium_access and not access.entitlements.talent_access
        with pytest.raises(ConflictError, match="déjà utilisé"):
            await FreeTestPilotService(session, settings).activate(user_id)
    async with AsyncSession(engine) as session:
        assert await count(session, Subscription) == 1
        assert await count(session, PaymentTransaction) == 0


@pytest.mark.parametrize("status", ["active", "trialing"])
@pytest.mark.parametrize("expired", [True, False])
async def test_existing_current_handled(database, settings, status, expired):
    engine, user_id = database
    async with AsyncSession(engine, expire_on_commit=False) as session:
        prior = Subscription(
            user_id=user_id,
            plan_code="annual",
            status=status,
            provider="existing",
            current_period_end=datetime.now(UTC) + timedelta(days=-1 if expired else 10),
        )
        session.add(prior)
        await session.commit()
        prior_id = prior.id
    if expired:
        await activate(engine, user_id, settings)
    else:
        with pytest.raises(ConflictError, match="déjà en cours"):
            await activate(engine, user_id, settings)
    async with AsyncSession(engine) as session:
        assert (await session.get(Subscription, prior_id)).status == (
            "replaced" if expired else status
        )
        assert await count(session, Subscription) == (2 if expired else 1)
        assert await count(session, PaymentTransaction) == 0


async def test_serialization_failure_rolls_back(database, settings):
    engine, user_id = database
    with patch(
        "app.api.v1.endpoints.subscriptions.SubscriptionResponse.model_validate",
        side_effect=ValueError("serialization"),
    ):
        with pytest.raises(ValueError):
            await activate(engine, user_id, settings)
    async with AsyncSession(engine) as session:
        assert await count(session, Subscription) == 0
    await activate(engine, user_id, settings)


@pytest.mark.parametrize("status", ["replaced", "cancelled"])
async def test_consumed_trial_cannot_restart_before_original_end(database, settings, status):
    engine, user_id = database
    trial = await activate(engine, user_id, settings)
    async with AsyncSession(engine) as session:
        row = await session.get(Subscription, trial.id)
        row.status = status
        await session.commit()
    with pytest.raises(ConflictError, match="déjà utilisé"):
        await activate(engine, user_id, settings)


async def test_all_expired_current_rows_replaced_atomically(database, settings):
    engine, user_id = database
    async with AsyncSession(engine, expire_on_commit=False) as session:
        rows = [
            Subscription(
                user_id=user_id,
                plan_code="monthly",
                status=status,
                current_period_end=datetime.now(UTC) - timedelta(days=1),
            )
            for status in ("active", "trialing")
        ]
        session.add_all(rows)
        await session.commit()
        ids = [row.id for row in rows]
    with patch(
        "app.api.v1.endpoints.subscriptions.SubscriptionResponse.model_validate",
        side_effect=ValueError("serialization"),
    ):
        with pytest.raises(ValueError):
            await activate(engine, user_id, settings)
    async with AsyncSession(engine) as session:
        assert [(await session.get(Subscription, id_)).status for id_ in ids] == [
            "active",
            "trialing",
        ]
    await activate(engine, user_id, settings)
    async with AsyncSession(engine) as session:
        assert all([(await session.get(Subscription, id_)).status == "replaced" for id_ in ids])
        assert await count(session, Subscription) == 3
        assert await count(session, PaymentTransaction) == 0
