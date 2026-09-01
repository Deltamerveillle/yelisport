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

    service.payments.get_by_provider_transaction.return_value = (
        other_transaction
    )

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

    service.subscriptions.get_current_for_user.return_value = (
        previous_subscription
    )

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
