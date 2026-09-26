"""Security tests for the SMS payment activation service."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.payment_service import PaymentService


def build_service() -> PaymentService:
    service = PaymentService.__new__(PaymentService)

    service.payments = SimpleNamespace(
        get_by_reference=AsyncMock(),
        get_by_provider_transaction=AsyncMock(),
        update=AsyncMock(),
    )

    service.subscriptions = SimpleNamespace(
        get_current_for_user=AsyncMock(),
        create=AsyncMock(),
        update=AsyncMock(),
    )

    return service


def pending_transaction() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        subscription_id=None,
        reference="SMS-PAY-001",
        provider="yeleni-pay",
        provider_transaction_id=None,
        plan_code="premium",
        amount_minor=500000,
        currency="XOF",
        duration_days=30,
        status="pending",
    )


def valid_period() -> tuple[datetime, datetime]:
    start = datetime.now(UTC)
    return start, start + timedelta(days=30)


@pytest.mark.asyncio
async def test_unknown_payment_reference_is_rejected() -> None:
    service = build_service()
    service.payments.get_by_reference.return_value = None

    start, end = valid_period()

    with pytest.raises(
        ValueError,
        match="Unknown payment reference",
    ):
        await service.confirm_verified_payment(
            reference="UNKNOWN",
            provider="yeleni-pay",
            provider_transaction_id="tx-001",
            amount_minor=500000,
            currency="XOF",
            period_start=start,
            period_end=end,
        )

    service.subscriptions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrong_provider_is_rejected() -> None:
    service = build_service()

    transaction = pending_transaction()
    service.payments.get_by_reference.return_value = transaction

    start, end = valid_period()

    with pytest.raises(
        ValueError,
        match="Payment provider mismatch",
    ):
        await service.confirm_verified_payment(
            reference=transaction.reference,
            provider="fake-provider",
            provider_transaction_id="tx-001",
            amount_minor=500000,
            currency="XOF",
            period_start=start,
            period_end=end,
        )

    service.subscriptions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_provider_transaction_cannot_be_reused() -> None:
    service = build_service()

    transaction = pending_transaction()
    service.payments.get_by_reference.return_value = transaction

    other_transaction = SimpleNamespace(
        id=uuid.uuid4(),
    )

    service.payments.get_by_provider_transaction.return_value = other_transaction

    start, end = valid_period()

    with pytest.raises(
        ValueError,
        match="Provider transaction already belongs to another payment",
    ):
        await service.confirm_verified_payment(
            reference=transaction.reference,
            provider=transaction.provider,
            provider_transaction_id="provider-tx-reused",
            amount_minor=500000,
            currency="XOF",
            period_start=start,
            period_end=end,
        )

    service.subscriptions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirmed_payment_replay_is_idempotent() -> None:
    service = build_service()

    transaction = pending_transaction()
    transaction.status = "succeeded"
    transaction.provider_transaction_id = "provider-tx-001"

    service.payments.get_by_reference.return_value = transaction
    service.payments.get_by_provider_transaction.return_value = transaction

    start, end = valid_period()

    result = await service.confirm_verified_payment(
        reference=transaction.reference,
        provider=transaction.provider,
        provider_transaction_id="provider-tx-001",
        amount_minor=500000,
        currency="XOF",
        period_start=start,
        period_end=end,
    )

    assert result is transaction

    service.subscriptions.create.assert_not_awaited()
    service.subscriptions.update.assert_not_awaited()
    service.payments.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_replay_with_different_provider_transaction_is_rejected() -> None:
    service = build_service()

    transaction = pending_transaction()
    transaction.status = "succeeded"
    transaction.provider_transaction_id = "provider-tx-original"

    service.payments.get_by_reference.return_value = transaction
    service.payments.get_by_provider_transaction.return_value = None

    start, end = valid_period()

    with pytest.raises(
        ValueError,
        match="Payment already confirmed with another provider transaction",
    ):
        await service.confirm_verified_payment(
            reference=transaction.reference,
            provider=transaction.provider,
            provider_transaction_id="provider-tx-fake",
            amount_minor=500000,
            currency="XOF",
            period_start=start,
            period_end=end,
        )

    service.subscriptions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_payment_replaces_previous_subscription() -> None:
    service = build_service()

    transaction = pending_transaction()

    service.payments.get_by_reference.return_value = transaction
    service.payments.get_by_provider_transaction.return_value = None

    previous_subscription = SimpleNamespace(
        id=uuid.uuid4(),
        status="active",
    )

    service.subscriptions.get_current_for_user.return_value = previous_subscription

    new_subscription_id = uuid.uuid4()

    async def create_subscription(subscription):
        subscription.id = new_subscription_id
        return subscription

    service.subscriptions.create.side_effect = create_subscription
    service.subscriptions.update.return_value = previous_subscription
    service.payments.update.return_value = transaction

    start, end = valid_period()

    result = await service.confirm_verified_payment(
        reference=transaction.reference,
        provider=transaction.provider,
        provider_transaction_id="provider-tx-new",
        amount_minor=500000,
        currency="XOF",
        period_start=start,
        period_end=end,
    )

    assert previous_subscription.status == "replaced"

    service.subscriptions.update.assert_awaited_once()
    service.subscriptions.create.assert_awaited_once()

    assert transaction.status == "succeeded"
    assert transaction.provider_transaction_id == "provider-tx-new"
    assert transaction.subscription_id == new_subscription_id

    assert result is transaction


@pytest.mark.asyncio
async def test_failed_payment_never_creates_subscription() -> None:
    service = build_service()

    transaction = pending_transaction()

    service.payments.get_by_reference.return_value = transaction
    service.payments.get_by_provider_transaction.return_value = None
    service.payments.update.return_value = transaction

    result = await service.mark_verified_payment_failed(
        reference=transaction.reference,
        provider=transaction.provider,
        provider_transaction_id="provider-tx-failed",
    )

    assert result.status == "failed"
    assert result.provider_transaction_id == "provider-tx-failed"

    service.subscriptions.create.assert_not_awaited()
    service.subscriptions.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_payment_cannot_be_changed_to_failed() -> None:
    service = build_service()

    transaction = pending_transaction()
    transaction.status = "succeeded"

    service.payments.get_by_reference.return_value = transaction

    with pytest.raises(
        ValueError,
        match="A successful payment cannot be changed to failed",
    ):
        await service.mark_verified_payment_failed(
            reference=transaction.reference,
            provider=transaction.provider,
            provider_transaction_id="provider-tx-001",
        )

    service.payments.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrong_payment_amount_is_rejected() -> None:
    service = build_service()

    transaction = pending_transaction()
    service.payments.get_by_reference.return_value = transaction

    start, end = valid_period()

    with pytest.raises(
        ValueError,
        match="Payment amount mismatch",
    ):
        await service.confirm_verified_payment(
            reference=transaction.reference,
            provider=transaction.provider,
            provider_transaction_id="provider-tx-amount",
            amount_minor=1,
            currency="XOF",
            period_start=start,
            period_end=end,
        )

    service.subscriptions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrong_payment_currency_is_rejected() -> None:
    service = build_service()

    transaction = pending_transaction()
    service.payments.get_by_reference.return_value = transaction

    start, end = valid_period()

    with pytest.raises(
        ValueError,
        match="Payment currency mismatch",
    ):
        await service.confirm_verified_payment(
            reference=transaction.reference,
            provider=transaction.provider,
            provider_transaction_id="provider-tx-currency",
            amount_minor=transaction.amount_minor,
            currency="USD",
            period_start=start,
            period_end=end,
        )

    service.subscriptions.create.assert_not_awaited()


def confirmation_service(duration=30):
    service = build_service()
    transaction = pending_transaction()
    transaction.duration_days = duration
    service.payments.get_by_reference.return_value = transaction
    service.payments.get_by_provider_transaction.return_value = None
    service.subscriptions.get_current_for_user.return_value = None
    service.subscriptions.create.return_value = SimpleNamespace(id=uuid.uuid4())
    return service, transaction


def facts(transaction, **changes):
    return (
        dict(
            reference=transaction.reference,
            provider=transaction.provider,
            provider_transaction_id="verified",
            amount_minor=transaction.amount_minor,
            currency=transaction.currency,
            period_start=datetime.now(UTC),
        )
        | changes
    )


async def test_term_derived_from_snapshot_without_provider_end():
    service, transaction = confirmation_service(17)
    arguments = facts(transaction)
    await service.confirm_verified_payment(**arguments)
    subscription = service.subscriptions.create.call_args.args[0]
    assert subscription.current_period_start == arguments["period_start"]
    assert subscription.current_period_end == arguments["period_start"] + timedelta(days=17)


@pytest.mark.parametrize("days", [29, 31, 0, -1])
async def test_provider_cannot_choose_a_different_term(days):
    service, transaction = confirmation_service()
    arguments = facts(transaction)
    with pytest.raises(ValueError, match="does not match purchased duration"):
        await service.confirm_verified_payment(
            **arguments,
            period_end=arguments["period_start"] + timedelta(days=days),
        )
    service.subscriptions.create.assert_not_awaited()
    service.subscriptions.update.assert_not_awaited()
    service.payments.update.assert_not_awaited()


@pytest.mark.parametrize("duration", [None, 0, -1, True, "30"])
async def test_missing_or_invalid_snapshot_fails_closed(duration):
    service, transaction = confirmation_service(duration)
    with pytest.raises(ValueError, match="duration snapshot"):
        await service.confirm_verified_payment(**facts(transaction))
    service.subscriptions.create.assert_not_awaited()


@pytest.mark.parametrize("field", ["period_start", "period_end"])
async def test_naive_timestamps_rejected(field):
    service, transaction = confirmation_service()
    arguments = facts(transaction)
    arguments[field] = datetime.now()
    with pytest.raises(ValueError, match="timezone-aware"):
        await service.confirm_verified_payment(**arguments)
    service.subscriptions.create.assert_not_awaited()


async def test_timezone_conversion_is_elapsed_utc_days_across_dst():
    from zoneinfo import ZoneInfo

    service, transaction = confirmation_service(2)
    start = datetime(2030, 3, 9, 12, tzinfo=ZoneInfo("America/New_York"))
    await service.confirm_verified_payment(**facts(transaction, period_start=start))
    subscription = service.subscriptions.create.call_args.args[0]
    assert subscription.current_period_start == start.astimezone(UTC)
    assert subscription.current_period_end == start.astimezone(UTC) + timedelta(days=2)
    assert subscription.current_period_end.tzinfo == UTC


async def test_expired_derived_term_rejected():
    service, transaction = confirmation_service()
    with pytest.raises(ValueError, match="already expired"):
        await service.confirm_verified_payment(
            **facts(
                transaction,
                period_start=datetime.now(UTC) - timedelta(days=31),
            )
        )
    service.subscriptions.create.assert_not_awaited()


async def test_datetime_overflow_is_validation_error():
    service, transaction = confirmation_service()
    with pytest.raises(ValueError, match="Invalid subscription period"):
        await service.confirm_verified_payment(
            **facts(
                transaction,
                period_start=datetime.max.replace(tzinfo=UTC),
            )
        )
    service.subscriptions.create.assert_not_awaited()


@pytest.mark.parametrize("duration", [None, 30])
async def test_succeeded_replay_even_after_expiry_does_not_recompute_term(duration):
    service, transaction = confirmation_service(duration)
    transaction.status = "succeeded"
    transaction.provider_transaction_id = "verified"
    result = await service.confirm_verified_payment(
        **facts(
            transaction,
            period_start=datetime.now(UTC) - timedelta(days=365),
        )
    )
    assert result is transaction
    service.subscriptions.create.assert_not_awaited()
    service.subscriptions.update.assert_not_awaited()
    service.payments.update.assert_not_awaited()


@pytest.mark.parametrize("status", ["failed", "cancelled"])
async def test_nonpending_payment_cannot_activate(status):
    service, transaction = confirmation_service()
    transaction.status = status
    with pytest.raises(ValueError, match="cannot be confirmed"):
        await service.confirm_verified_payment(**facts(transaction))
    service.subscriptions.create.assert_not_awaited()
