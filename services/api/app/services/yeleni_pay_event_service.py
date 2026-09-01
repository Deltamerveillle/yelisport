"""Idempotent processing of trusted YELENI Pay events."""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.yeleni_pay_event import YeleniPayEvent
from app.repositories.yeleni_pay_event_repository import (
    YeleniPayEventRepository,
)
from app.schemas.yeleni_pay import (
    YeleniPayPaymentConfirmed,
    YeleniPayPaymentFailed,
)
from app.services.payment_service import PaymentService


class YeleniPayEventService:
    """Processes trusted YELENI Pay events exactly once."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.events = YeleniPayEventRepository(session)
        self.payments = PaymentService(session)

    async def _create_event(
        self,
        *,
        event_id: str,
        event_type: str,
        reference: str,
    ) -> tuple[YeleniPayEvent, bool]:
        existing = await self.events.get_by_event_id(event_id)

        if existing is not None:
            return existing, False

        event = YeleniPayEvent(
            event_id=event_id,
            event_type=event_type,
            reference=reference,
            status="received",
        )

        try:
            event = await self.events.create(event)
            return event, True

        except IntegrityError:
            existing = await self.events.get_by_event_id(event_id)

            if existing is None:
                raise

            return existing, False

    async def process_confirmed(
        self,
        payload: YeleniPayPaymentConfirmed,
    ) -> YeleniPayEvent:
        event, should_process = await self._create_event(
            event_id=payload.event_id,
            event_type=payload.event_type,
            reference=payload.reference,
        )

        if not should_process:
            return event

        try:
            await self.payments.confirm_verified_payment(
                reference=payload.reference,
                provider=payload.provider,
                provider_transaction_id=payload.provider_transaction_id,
                amount_minor=payload.amount_minor,
                currency=payload.currency,
                period_start=payload.period_start,
                period_end=payload.period_end,
                provider_customer_id=payload.provider_customer_id,
                provider_subscription_id=payload.provider_subscription_id,
            )

            event.status = "processed"
            event.processed_at = datetime.now(UTC)

            await self.events.update(event)

            return event

        except Exception:
            event.status = "failed"
            await self.events.update(event)
            raise

    async def process_failed(
        self,
        payload: YeleniPayPaymentFailed,
    ) -> YeleniPayEvent:
        event, should_process = await self._create_event(
            event_id=payload.event_id,
            event_type=payload.event_type,
            reference=payload.reference,
        )

        if not should_process:
            return event

        try:
            await self.payments.mark_verified_payment_failed(
                reference=payload.reference,
                provider=payload.provider,
                provider_transaction_id=payload.provider_transaction_id,
            )

            event.status = "processed"
            event.processed_at = datetime.now(UTC)

            await self.events.update(event)

            return event

        except Exception:
            event.status = "failed"
            await self.events.update(event)
            raise
