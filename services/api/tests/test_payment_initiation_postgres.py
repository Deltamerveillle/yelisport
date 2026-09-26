"""Real commits/concurrency, exclusively in an opt-in disposable PostgreSQL schema."""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.models.payment_transaction import PaymentTransaction
from app.models.subscription import Subscription
from app.models.user import User
from app.services.payment_initiation_service import PaymentInitiationService
from app.services.payment_service import PaymentService
from tests.api.test_payments import plan


@pytest.fixture
async def database():
    url = os.environ.get("SMS24_MIGRATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set SMS24_MIGRATION_TEST_DATABASE_URL to disposable PostgreSQL")
    schema = "payment_test_" + uuid.uuid4().hex
    admin = create_async_engine(url, poolclass=NullPool)
    engine = create_async_engine(
        url, poolclass=NullPool, connect_args={"server_settings": {"search_path": schema}}
    )
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync: Base.metadata.create_all(
                    sync,
                    tables=[m.__table__ for m in (User, Subscription, PaymentTransaction)],
                )
            )
        user_id = uuid.uuid4()
        async with AsyncSession(engine) as session:
            session.add(User(id=user_id, email="payment@example.test"))
            await session.commit()
        yield engine, user_id
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()


async def initiate(session, user_id, **changes):
    return await PaymentInitiationService(session, [plan(**changes)]).initiate(
        user_id=user_id,
        plan_code="test_offer_v1",
    )


async def count(session, model):
    return await session.scalar(select(func.count()).select_from(model))


async def test_commit_replay_price_snapshot_and_verified_activation(database):
    engine, user_id = database
    async with AsyncSession(engine, expire_on_commit=False) as session:
        row = await initiate(session, user_id)
        identity, reference = row.id, row.reference
        assert row.user_id == user_id and row.subscription_id is None
        assert row.duration_days == 30
        assert (row.amount_minor, row.currency, row.status) == (1234, "XOF", "pending")
        assert await count(session, Subscription) == 0
        await session.commit()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        replay = await initiate(
            session, user_id, amount_minor=9999, currency="EUR", duration_days=90
        )
        assert replay.id == identity and replay.amount_minor == 1234 and replay.currency == "XOF"
        assert replay.duration_days == 30
        assert await count(session, PaymentTransaction) == 1
        now = datetime.now(UTC)
        kwargs = dict(
            reference=reference,
            provider="manual",
            provider_transaction_id="verified-1",
            amount_minor=1234,
            currency="XOF",
            period_start=now,
            period_end=now + timedelta(days=30),
        )
        service = PaymentService(session)
        await service.confirm_verified_payment(**kwargs)
        await service.confirm_verified_payment(**kwargs)
        assert await count(session, Subscription) == 1
        await session.commit()
    async with AsyncSession(engine) as session:
        row = await session.get(PaymentTransaction, identity)
        assert row.status == "succeeded" and row.subscription_id is not None


async def test_rollback_no_pending_row(database):
    engine, user_id = database
    async with AsyncSession(engine) as session:
        await initiate(session, user_id)
        await session.rollback()
    async with AsyncSession(engine) as session:
        assert await count(session, PaymentTransaction) == 0
        assert await count(session, Subscription) == 0


async def test_concurrent_initiation_reuses_one_pending(database):
    engine, user_id = database

    async def run():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = await initiate(session, user_id)
            await session.commit()
            return row.id

    ids = await asyncio.wait_for(asyncio.gather(run(), run()), timeout=10)
    assert ids[0] == ids[1]
    async with AsyncSession(engine) as session:
        assert await count(session, PaymentTransaction) == 1


async def test_concurrent_confirmation_only_one_subscription(database):
    engine, user_id = database
    async with AsyncSession(engine, expire_on_commit=False) as session:
        row = await initiate(session, user_id)
        reference = row.reference
        await session.commit()

    async def run():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            now = datetime.now(UTC)
            row = await PaymentService(session).confirm_verified_payment(
                reference=reference,
                provider="manual",
                provider_transaction_id="verified-1",
                amount_minor=1234,
                currency="XOF",
                period_start=now,
                period_end=now + timedelta(days=30),
            )
            await session.commit()
            return row.subscription_id

    ids = await asyncio.wait_for(asyncio.gather(run(), run()), timeout=10)
    assert ids[0] == ids[1]
    async with AsyncSession(engine) as session:
        assert await count(session, Subscription) == 1


async def test_reference_and_pending_are_user_scoped(database):
    engine, user_id = database
    async with AsyncSession(engine) as session:
        other = uuid.uuid4()
        session.add(User(id=other, email="other@example.test"))
        await session.flush()
        a, b = await initiate(session, user_id), await initiate(session, other)
        assert a.reference != b.reference and a.id != b.id
        assert a.reference.startswith("SMS-") and len(a.reference) > 40


async def test_http_boundary_commits_pending(database):
    from types import SimpleNamespace

    from app.api.v1.endpoints.payments import initiate_payment
    from app.core.config import Settings
    from app.schemas.payment import PaymentInitiationRequest

    engine, user_id = database
    async with AsyncSession(engine, expire_on_commit=False) as session:
        response = await initiate_payment(
            PaymentInitiationRequest(plan_code="test_offer_v1"),
            SimpleNamespace(id=str(user_id)),
            session,
            Settings(sms_commercial_plans=[plan()]),
        )
    async with AsyncSession(engine) as session:
        row = await session.get(PaymentTransaction, response.id)
        assert row.status == "pending" and row.user_id == user_id
        assert await count(session, Subscription) == 0


async def test_http_serialization_failure_rolls_back_pending(database):
    from types import SimpleNamespace
    from unittest.mock import patch

    from app.api.v1.endpoints.payments import initiate_payment
    from app.core.config import Settings
    from app.schemas.payment import PaymentInitiationRequest

    engine, user_id = database
    async with AsyncSession(engine, expire_on_commit=False) as session:
        with patch(
            "app.api.v1.endpoints.payments.PaymentResponse.model_validate",
            side_effect=ValueError("serialization failed"),
        ):
            with pytest.raises(ValueError):
                await initiate_payment(
                    PaymentInitiationRequest(plan_code="test_offer_v1"),
                    SimpleNamespace(id=str(user_id)),
                    session,
                    Settings(sms_commercial_plans=[plan()]),
                )
    async with AsyncSession(engine) as session:
        assert await count(session, PaymentTransaction) == 0
        assert await count(session, Subscription) == 0
