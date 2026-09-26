"""Secure provider-neutral payment activation service."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_transaction import PaymentTransaction
from app.models.subscription import Subscription
from app.repositories.payment_transaction_repository import (
    PaymentTransactionRepository,
)
from app.repositories.subscription_repository import SubscriptionRepository


class PaymentService:
    """Internal service applying verified payment results to SMS access."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.payments = PaymentTransactionRepository(session)
        self.subscriptions = SubscriptionRepository(session)

    async def confirm_verified_payment(
        self,
        *,
        reference: str,
        provider: str,
        provider_transaction_id: str,
        amount_minor: int,
        currency: str,
        period_start: datetime,
        period_end: datetime | None = None,
        provider_customer_id: str | None = None,
        provider_subscription_id: str | None = None,
    ) -> PaymentTransaction:
        """
        Activate SMS access after a payment provider has been verified.

        This method is internal and must never be exposed directly as a
        user-controlled endpoint.
        """

        transaction = await self.payments.get_by_reference(reference)

        if transaction is None:
            raise ValueError("Unknown payment reference")

        if transaction.provider != provider:
            raise ValueError("Payment provider mismatch")

        if transaction.amount_minor != amount_minor:
            raise ValueError("Payment amount mismatch")

        if transaction.currency.upper() != currency.upper():
            raise ValueError("Payment currency mismatch")

        existing_provider_transaction = await self.payments.get_by_provider_transaction(
            provider,
            provider_transaction_id,
        )

        if (
            existing_provider_transaction is not None
            and existing_provider_transaction.id != transaction.id
        ):
            raise ValueError("Provider transaction already belongs to another payment")

        # Idempotent replay of an already processed payment.
        if transaction.status == "succeeded":
            if transaction.provider_transaction_id != provider_transaction_id:
                raise ValueError("Payment already confirmed with another provider " "transaction")

            return transaction

        if transaction.status != "pending":
            raise ValueError(f"Payment cannot be confirmed from status " f"{transaction.status}")

        # Legacy pending payments cannot acquire a term from today's catalogue.
        duration = transaction.duration_days
        if type(duration) is not int or duration <= 0:
            raise ValueError("Payment has no valid purchased duration snapshot")
        if not isinstance(period_start, datetime) or period_start.utcoffset() is None:
            raise ValueError("Subscription period start must be timezone-aware")
        try:
            period_start = period_start.astimezone(UTC)
            derived_end = period_start + timedelta(days=duration)
        except (OverflowError, ValueError) as exc:
            raise ValueError("Invalid subscription period") from exc
        if period_end is not None:
            if not isinstance(period_end, datetime) or period_end.utcoffset() is None:
                raise ValueError("Subscription period end must be timezone-aware")
            if period_end.astimezone(UTC) != derived_end:
                raise ValueError("Subscription period does not match purchased duration")
        if derived_end <= datetime.now(UTC):
            raise ValueError("Subscription period already expired")
        period_end = derived_end

        current_subscription = await self.subscriptions.get_current_for_user(transaction.user_id)

        # Prevent multiple concurrent active subscriptions.
        if current_subscription is not None:
            current_subscription.status = "replaced"
            await self.subscriptions.update(current_subscription)

        subscription = Subscription(
            user_id=transaction.user_id,
            plan_code=transaction.plan_code,
            status="active",
            provider=provider,
            provider_customer_id=provider_customer_id,
            provider_subscription_id=provider_subscription_id,
            current_period_start=period_start,
            current_period_end=period_end,
        )

        subscription = await self.subscriptions.create(subscription)

        transaction.provider_transaction_id = provider_transaction_id
        transaction.subscription_id = subscription.id
        transaction.status = "succeeded"

        await self.payments.update(transaction)

        return transaction

    async def mark_verified_payment_failed(
        self,
        *,
        reference: str,
        provider: str,
        provider_transaction_id: str | None = None,
    ) -> PaymentTransaction:
        """Record a verified provider failure without granting SMS access."""

        transaction = await self.payments.get_by_reference(reference)

        if transaction is None:
            raise ValueError("Unknown payment reference")

        if transaction.provider != provider:
            raise ValueError("Payment provider mismatch")

        if transaction.status == "succeeded":
            raise ValueError("A successful payment cannot be changed to failed")

        if transaction.status == "failed":
            return transaction

        if provider_transaction_id is not None:
            existing_provider_transaction = await self.payments.get_by_provider_transaction(
                provider,
                provider_transaction_id,
            )

            if (
                existing_provider_transaction is not None
                and existing_provider_transaction.id != transaction.id
            ):
                raise ValueError("Provider transaction already belongs to another payment")

            transaction.provider_transaction_id = provider_transaction_id

        transaction.status = "failed"

        await self.payments.update(transaction)

        return transaction
