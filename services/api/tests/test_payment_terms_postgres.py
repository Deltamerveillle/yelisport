"""Duration migration and atomic activation on isolated disposable PostgreSQL schemas."""

import importlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_transaction import PaymentTransaction
from app.models.subscription import Subscription
from app.services.payment_service import PaymentService
from tests import test_payment_initiation_postgres as foundation
from tests.test_payment_initiation_postgres import count, initiate

database = foundation.database

M41 = importlib.import_module(
    "app.db.migrations.versions.20260926_0041_add_payment_duration_snapshot"
)


def migrate(connection, direction):
    with Operations.context(MigrationContext.configure(connection)):
        getattr(M41, direction)()


def confirmation(row, **changes):
    return (
        dict(
            reference=row.reference,
            provider="yeleni-pay",
            provider_transaction_id="verified",
            amount_minor=1234,
            currency="XOF",
            period_start=datetime.now(UTC),
        )
        | changes
    )


async def test_0041_round_trip_preserves_legacy_rows(database):
    engine, user_id = database
    async with AsyncSession(engine, expire_on_commit=False) as session:
        row = await initiate(session, user_id)
        identity = row.id
        await session.commit()
    # Start at the 0040 table shape and retain a historical payment throughout.
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: migrate(sync, "downgrade"))
        for direction in ("upgrade", "downgrade", "upgrade"):
            await connection.run_sync(lambda sync, d=direction: migrate(sync, d))
            columns = await connection.run_sync(
                lambda sync: {
                    c["name"]: c for c in inspect(sync).get_columns("payment_transactions")
                }
            )
            assert ("duration_days" in columns) == (direction == "upgrade")
            if direction == "upgrade":
                assert columns["duration_days"]["nullable"]
                assert columns["duration_days"]["default"] is None
                assert (
                    await connection.scalar(
                        text("SELECT duration_days FROM payment_transactions WHERE id=:id"),
                        {"id": identity},
                    )
                    is None
                )
        constraints = await connection.run_sync(
            lambda sync: inspect(sync).get_check_constraints("payment_transactions")
        )
        assert {c["name"] for c in constraints} >= {
            "ck_payment_transactions_amount_positive",
            "ck_payment_transactions_duration_positive",
        }
    async with AsyncSession(engine) as session:
        row = await session.get(PaymentTransaction, identity)
        assert row.reference and row.amount_minor == 1234 and row.status == "pending"
        assert row.duration_days is None
        # Reuse never backfills a legacy duration from today's catalogue.
        reused = await initiate(session, user_id, duration_days=90)
        assert reused.id == identity and reused.duration_days is None
        with pytest.raises(ValueError, match="duration snapshot"):
            await PaymentService(session).confirm_verified_payment(**confirmation(row))
        assert await count(session, Subscription) == 0


@pytest.mark.parametrize("duration", [0, -1])
async def test_database_rejects_nonpositive_duration(database, duration):
    engine, user_id = database
    async with AsyncSession(engine) as session:
        row = await initiate(session, user_id)
        async with session.begin_nested() as savepoint:
            row.duration_days = duration
            with pytest.raises(IntegrityError):
                await session.flush()
            await savepoint.rollback()


async def test_activation_term_and_read_only_replay(database):
    engine, user_id = database
    async with AsyncSession(engine, expire_on_commit=False) as session:
        row = await initiate(session, user_id, duration_days=17)
        arguments = confirmation(row)
        await PaymentService(session).confirm_verified_payment(**arguments)
        identity = row.subscription_id
        await session.commit()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        subscription = await session.get(Subscription, identity)
        original = subscription.current_period_start, subscription.current_period_end
        assert original == (
            arguments["period_start"],
            arguments["period_start"] + timedelta(days=17),
        )
        await PaymentService(session).confirm_verified_payment(
            **(arguments | {"period_start": datetime.now(UTC) - timedelta(days=365)})
        )
        await session.commit()
        await session.refresh(subscription)
        assert (subscription.current_period_start, subscription.current_period_end) == original
        assert await count(session, Subscription) == 1


async def test_partial_confirmation_failure_rolls_back_all_changes(database):
    engine, user_id = database
    async with AsyncSession(engine, expire_on_commit=False) as session:
        row = await initiate(session, user_id)
        reference, identity = row.reference, row.id
        prior = Subscription(user_id=user_id, plan_code="old", status="active", provider="manual")
        session.add(prior)
        await session.commit()
        prior_id = prior.id
    async with AsyncSession(engine) as session:
        row = await session.get(PaymentTransaction, identity)
        service = PaymentService(session)
        service.payments.update = AsyncMock(
            side_effect=RuntimeError("failure after subscription flush")
        )
        with pytest.raises(RuntimeError):
            await service.confirm_verified_payment(**confirmation(row))
        await session.rollback()
    async with AsyncSession(engine) as session:
        row = (
            await session.scalars(
                select(PaymentTransaction).where(
                    PaymentTransaction.reference == reference,
                )
            )
        ).one()
        assert row.status == "pending" and row.subscription_id is None
        assert row.provider_transaction_id is None
        assert await count(session, Subscription) == 1
        assert (await session.get(Subscription, prior_id)).status == "active"
