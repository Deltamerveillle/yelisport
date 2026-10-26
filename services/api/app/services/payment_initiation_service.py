"""Local payment intentions. No provider network calls or subscription activation."""

import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.payment_transaction import PaymentTransaction
from app.repositories.payment_transaction_repository import PaymentTransactionRepository
from app.schemas.payment import CommercialPlan


class PaymentInitiationService:
    def __init__(self, session: AsyncSession, plans: list[CommercialPlan]) -> None:
        self.payments = PaymentTransactionRepository(session)
        self.plans = {plan.plan_code: plan for plan in plans}

    async def initiate(self, *, user_id: uuid.UUID, plan_code: str) -> PaymentTransaction:
        plan = self.plans.get(plan_code)
        if plan is None:
            raise NotFoundError("Offre introuvable")
        if not plan.active or not plan.purchasable:
            raise ConflictError("Offre indisponible à l'achat")
        # Serializes initiation and verified activation for this user until outer commit.
        await self.payments.lock_user(user_id)
        existing = await self.payments.get_pending_for_plan(user_id, plan_code)
        if existing is not None:
            return existing
        return await self.payments.create(
            PaymentTransaction(
                reference="SMS-" + secrets.token_urlsafe(32),
                user_id=user_id,
                subscription_id=None,
                provider="yeleni-pay",
                plan_code=plan.plan_code,
                amount_minor=plan.amount_minor,
                currency=plan.currency,
                duration_days=plan.duration_days,
                status="pending",
            )
        )

    async def get_owned(
        self, *, user_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> PaymentTransaction:
        transaction = await self.payments.get_by_id(transaction_id)
        if transaction is None or transaction.user_id != user_id:
            raise NotFoundError("Paiement introuvable")
        return transaction
