"""Tests for idempotent YELENI Pay event processing."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.yeleni_pay import (
    YeleniPayPaymentConfirmed,
    YeleniPayPaymentFailed,
)
from app.services.yeleni_pay_event_service import YeleniPayEventService


def build_service() -> YeleniPayEventService:
    service = YeleniPayEventService.__new__(YeleniPayEventService)

    service.events = SimpleNamespace(
        get_by_event_id=AsyncMock(),
        create=AsyncMock(),
        update=AsyncMock(),
    )

    service.payments = SimpleNamespace(
        confirm_verified_payment=AsyncMock(),
        mark_verified_payment_failed=AsyncMock(),
    )

    return service


def confirmed_payload(
    event_id: str = "evt-confirmed-001",
) -> YeleniPayPaymentConfirmed:
    now = datetime.now(UTC)

    return YeleniPayPaymentConfirmed(
        event_id=event_id,
        event_type="payment.confirmed",
        reference="SMS-PAY-001",
        provider="yeleni-pay",
        provider_transaction_id="provider-tx-001",
        amount_minor=500000,
        currency="XOF",
        period_start=now,
        period_end=now + timedelta(days=30),
        provider_customer_id="customer-001",
        provider_subscription_id="subscription-001",
    )


def failed_payload(
    event_id: str = "evt-failed-001",
) -> YeleniPayPaymentFailed:
    return YeleniPayPaymentFailed(
        event_id=event_id,
        event_type="payment.failed",
        reference="SMS-PAY-002",
        provider="yeleni-pay",
        provider_transaction_id="provider-tx-002",
    )


@pytest.mark.asyncio
async def test_confirmed_event_is_processed_once() -> None:
    service = build_service()

    service.events.get_by_event_id.return_value = None

    created_event = SimpleNamespace(
        event_id="evt-confirmed-001",
        event_type="payment.confirmed",
        reference="SMS-PAY-001",
        status="received",
        processed_at=None,
    )

    service.events.create.return_value = created_event
    service.events.update.return_value = created_event

    result = await service.process_confirmed(
        confirmed_payload()
    )

    service.payments.confirm_verified_payment.assert_awaited_once()

    assert result.status == "processed"
    assert result.processed_at is not None


@pytest.mark.asyncio
async def test_duplicate_confirmed_event_is_not_reprocessed() -> None:
    service = build_service()

    existing_event = SimpleNamespace(
        event_id="evt-confirmed-001",
        status="processed",
    )

    service.events.get_by_event_id.return_value = existing_event

    result = await service.process_confirmed(
        confirmed_payload()
    )

    assert result is existing_event

    service.events.create.assert_not_awaited()
    service.payments.confirm_verified_payment.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_payment_event_never_activates_subscription() -> None:
    service = build_service()

    service.events.get_by_event_id.return_value = None

    created_event = SimpleNamespace(
        event_id="evt-failed-001",
        event_type="payment.failed",
        reference="SMS-PAY-002",
        status="received",
        processed_at=None,
    )

    service.events.create.return_value = created_event
    service.events.update.return_value = created_event

    result = await service.process_failed(
        failed_payload()
    )

    service.payments.mark_verified_payment_failed.assert_awaited_once()
    service.payments.confirm_verified_payment.assert_not_awaited()

    assert result.status == "processed"
    assert result.processed_at is not None


@pytest.mark.asyncio
async def test_duplicate_failed_event_is_not_reprocessed() -> None:
    service = build_service()

    existing_event = SimpleNamespace(
        event_id="evt-failed-001",
        status="processed",
    )

    service.events.get_by_event_id.return_value = existing_event

    result = await service.process_failed(
        failed_payload()
    )

    assert result is existing_event

    service.events.create.assert_not_awaited()
    service.payments.mark_verified_payment_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_processing_error_marks_event_failed() -> None:
    service = build_service()

    service.events.get_by_event_id.return_value = None

    created_event = SimpleNamespace(
        event_id="evt-confirmed-001",
        event_type="payment.confirmed",
        reference="SMS-PAY-001",
        status="received",
        processed_at=None,
    )

    service.events.create.return_value = created_event
    service.events.update.return_value = created_event

    service.payments.confirm_verified_payment.side_effect = ValueError(
        "Payment provider mismatch"
    )

    with pytest.raises(
        ValueError,
        match="Payment provider mismatch",
    ):
        await service.process_confirmed(
            confirmed_payload()
        )

    assert created_event.status == "failed"
    service.events.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_duplicate_event_is_not_reprocessed() -> None:
    """A database uniqueness collision must behave like an idempotent replay."""

    from sqlalchemy.exc import IntegrityError

    service = build_service()

    existing_event = SimpleNamespace(
        event_id="evt-confirmed-001",
        event_type="payment.confirmed",
        reference="SMS-PAY-001",
        status="processed",
        processed_at=datetime.now(UTC),
    )

    service.events.get_by_event_id.side_effect = [
        None,
        existing_event,
    ]

    service.events.create.side_effect = IntegrityError(
        statement="INSERT INTO yeleni_pay_events ...",
        params={},
        orig=Exception("duplicate event_id"),
    )

    result = await service.process_confirmed(
        confirmed_payload()
    )

    assert result is existing_event

    assert service.events.get_by_event_id.await_count == 2
    service.events.create.assert_awaited_once()

    service.payments.confirm_verified_payment.assert_not_awaited()
