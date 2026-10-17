"""Gateway identities, retries and migration on disposable PostgreSQL only."""

import asyncio
import importlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.payment_transaction import PaymentTransaction
from app.models.subscription import Subscription
from app.models.yeleni_pay_event import YeleniPayEvent
from app.models.yeleni_pay_rail_transaction import YeleniPayRailTransaction as Rail
from app.repositories.yeleni_pay_rail_repository import YeleniPayRailRepository
from app.schemas.payment_rail import RailInitializationResult
from app.schemas.yeleni_pay import YeleniPayPaymentConfirmed
from app.services.payment_service import PaymentService
from app.services.yeleni_pay_event_service import YeleniPayEventService
from tests import test_payment_initiation_postgres as foundation

database = foundation.database
migration = importlib.import_module(
    "app.db.migrations.versions.20260927_0042_add_yeleni_pay_rail_transactions"
)


def migrate(connection, direction):
    with Operations.context(MigrationContext.configure(connection)):
        getattr(migration, direction)()


@pytest.fixture
async def gateway(database):
    engine, user_id = database
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: migrate(sync, "upgrade"))
        await connection.run_sync(lambda sync: YeleniPayEvent.__table__.create(sync))
    async with AsyncSession(engine, expire_on_commit=False) as session:
        payment = await foundation.initiate(session, user_id)
        assert payment.provider == "yeleni-pay"
        await session.commit()
        yield engine, user_id, payment.reference


async def test_migration_roundtrip_preserves_sms_payment(database):
    engine, user_id = database
    async with AsyncSession(engine, expire_on_commit=False) as session:
        payment = await foundation.initiate(session, user_id)
        payment.provider = "manual"  # historical record remains untouched by migration
        await session.commit()
        identity = payment.id
    async with engine.begin() as connection:
        for direction in ("upgrade", "downgrade", "upgrade"):
            await connection.run_sync(lambda sync, d=direction: migrate(sync, d))
            exists = await connection.run_sync(
                lambda sync: inspect(sync).has_table(Rail.__tablename__)
            )
            assert exists == (direction == "upgrade")
    async with AsyncSession(engine) as session:
        payment = await session.get(PaymentTransaction, identity)
        assert payment.provider == "manual" and payment.status == "pending"
        assert payment.duration_days == 30
        replay = await foundation.initiate(session, user_id)
        assert replay.id == identity and replay.provider == "manual"
        now = datetime.now(UTC)
        await PaymentService(session).confirm_verified_payment(
            reference=payment.reference,
            provider="manual",
            provider_transaction_id="old-verified",
            amount_minor=payment.amount_minor,
            currency=payment.currency,
            period_start=now,
        )
        assert payment.status == "succeeded"


@pytest.mark.parametrize("code", ["ecolepay", "cinetpay", "flutterwave", "other-psp"])
async def test_provider_neutral_prepare_and_idempotent_binding(gateway, code):
    engine, _, reference = gateway
    async with AsyncSession(engine, expire_on_commit=False) as session:
        repository = YeleniPayRailRepository(session)
        rail, request = await repository.prepare(payment_reference=reference, rail_code=code)
        initial_time = rail.updated_at
        replay, replay_request = await repository.prepare(
            payment_reference=reference, rail_code=code
        )
        assert replay.id == request.idempotency_key == rail.id and replay_request == request
        assert replay.updated_at == initial_time
        assert set(request.model_dump()) == {
            "idempotency_key",
            "payment_reference",
            "amount_minor",
            "currency",
        }
        result = RailInitializationResult(external_transaction_id="external-1")
        await repository.record_initialization(
            payment_reference=reference, rail_code=code, result=result
        )
        updated = rail.updated_at
        await repository.record_initialization(
            payment_reference=reference, rail_code=code, result=result
        )
        assert rail.updated_at == updated and rail.status == "pending"
        payment = (await session.scalars(select(PaymentTransaction))).one()
        assert (payment.amount_minor, payment.currency, payment.duration_days, payment.status) == (
            1234,
            "XOF",
            30,
            "pending",
        )
        assert payment.subscription_id is None
        assert await foundation.count(session, Subscription) == 0
        await session.commit()


async def test_cannot_replace_rail_or_external_identity(gateway):
    engine, _, reference = gateway
    async with AsyncSession(engine) as session:
        repository = YeleniPayRailRepository(session)
        await repository.record_initialization(
            payment_reference=reference,
            rail_code="rail-a",
            result=RailInitializationResult(external_transaction_id="one"),
        )
        with pytest.raises(ConflictError):
            await repository.prepare(payment_reference=reference, rail_code="rail-b")
        with pytest.raises(ConflictError):
            await repository.record_initialization(
                payment_reference=reference,
                rail_code="rail-a",
                result=RailInitializationResult(external_transaction_id="two"),
            )


async def test_external_uniqueness_scoped_to_rail(gateway):
    engine, user_id, reference = gateway
    async with AsyncSession(engine) as session:
        payment = (await session.scalars(select(PaymentTransaction))).one()
        for code in ("rail-a", "rail-b"):
            other = PaymentTransaction(
                reference=str(uuid.uuid4()),
                user_id=user_id,
                provider="yeleni-pay",
                plan_code=payment.plan_code,
                amount_minor=1234,
                currency="XOF",
                duration_days=30,
            )
            session.add(other)
            await session.flush()
            session.add(
                Rail(
                    payment_transaction_id=other.id, rail_code=code, external_transaction_id="same"
                )
            )
            await session.flush()
        async with session.begin_nested():
            session.add(
                Rail(
                    payment_transaction_id=payment.id,
                    rail_code="rail-a",
                    external_transaction_id="same",
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()


async def test_payment_has_only_one_rail_transaction(gateway):
    engine, _, reference = gateway
    async with AsyncSession(engine) as session:
        rail, _ = await YeleniPayRailRepository(session).prepare(
            payment_reference=reference, rail_code="a"
        )
        async with session.begin_nested():
            session.add(Rail(payment_transaction_id=rail.payment_transaction_id, rail_code="b"))
            with pytest.raises(IntegrityError):
                await session.flush()


async def test_concurrent_preparation_returns_same_id(gateway):
    engine, _, reference = gateway

    async def prepare():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            rail, _ = await YeleniPayRailRepository(session).prepare(
                payment_reference=reference, rail_code="rail"
            )
            await session.commit()
            return rail.id

    ids = await asyncio.wait_for(asyncio.gather(prepare(), prepare()), timeout=10)
    assert ids[0] == ids[1]


async def test_trusted_event_replay_and_subscription_boundary(gateway):
    engine, _, reference = gateway
    async with AsyncSession(engine, expire_on_commit=False) as session:
        rail, _ = await YeleniPayRailRepository(session).prepare(
            payment_reference=reference, rail_code="rail"
        )
        now = datetime.now(UTC)
        event = YeleniPayPaymentConfirmed(
            event_id="trusted-event",
            event_type="payment.confirmed",
            reference=reference,
            provider="yeleni-pay",
            provider_transaction_id=str(rail.id),
            amount_minor=1234,
            currency="XOF",
            period_start=now,
            period_end=now + timedelta(days=30),
        )
        service = YeleniPayEventService(session)
        first = await service.process_confirmed(event)
        second = await service.process_confirmed(event)
        assert first.id == second.id and first.status == "processed"
        assert await foundation.count(session, Subscription) == 1
        assert await foundation.count(session, YeleniPayEvent) == 1
        await session.commit()


async def test_rollback_discards_local_rail(gateway):
    engine, _, reference = gateway
    async with AsyncSession(engine) as session:
        await YeleniPayRailRepository(session).prepare(
            payment_reference=reference, rail_code="rail"
        )
        await session.rollback()
    async with AsyncSession(engine) as session:
        assert await foundation.count(session, Rail) == 0
        assert (await session.scalars(select(PaymentTransaction))).one().status == "pending"


@pytest.mark.parametrize("status", ["succeeded", "failed"])
async def test_terminal_rail_cannot_be_reinitialized(gateway, status):
    engine, _, reference = gateway
    async with AsyncSession(engine) as session:
        repository = YeleniPayRailRepository(session)
        rail, _ = await repository.prepare(payment_reference=reference, rail_code="rail")
        rail.status = status
        await session.flush()
        with pytest.raises(ConflictError):
            await repository.prepare(payment_reference=reference, rail_code="rail")
