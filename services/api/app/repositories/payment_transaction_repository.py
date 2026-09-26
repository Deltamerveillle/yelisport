"""Repository for SMS payment transactions."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_transaction import PaymentTransaction
from app.models.user import User


class PaymentTransactionRepository:
    """Database operations for SMS payment transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_user(self, user_id: uuid.UUID) -> None:
        """Shared lock order: user first, then payment; caller owns transaction."""
        result = await self.session.execute(
            select(User.id).where(User.id == user_id).with_for_update()
        )
        result.scalar_one()

    async def get_pending_for_plan(self, user_id: uuid.UUID, plan_code: str):
        result = await self.session.execute(
            select(PaymentTransaction)
            .where(
                PaymentTransaction.user_id == user_id,
                PaymentTransaction.plan_code == plan_code,
                PaymentTransaction.status == "pending",
            )
            .order_by(PaymentTransaction.created_at, PaymentTransaction.id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        transaction: PaymentTransaction,
    ) -> PaymentTransaction:
        self.session.add(transaction)
        await self.session.flush()
        await self.session.refresh(transaction)
        return transaction

    async def get_by_id(
        self,
        transaction_id: uuid.UUID,
    ) -> PaymentTransaction | None:
        result = await self.session.execute(
            select(PaymentTransaction).where(PaymentTransaction.id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def get_by_reference(
        self,
        reference: str,
    ) -> PaymentTransaction | None:
        result = await self.session.execute(
            select(PaymentTransaction).where(PaymentTransaction.reference == reference)
        )
        transaction = result.scalar_one_or_none()
        if transaction is None:
            return None
        await self.lock_user(transaction.user_id)
        result = await self.session.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.reference == reference)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_provider_transaction(
        self,
        provider: str,
        provider_transaction_id: str,
    ) -> PaymentTransaction | None:
        result = await self.session.execute(
            select(PaymentTransaction).where(
                PaymentTransaction.provider == provider,
                PaymentTransaction.provider_transaction_id == provider_transaction_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user_id(
        self,
        user_id: uuid.UUID,
    ) -> Sequence[PaymentTransaction]:
        result = await self.session.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.user_id == user_id)
            .order_by(PaymentTransaction.created_at.desc())
        )
        return result.scalars().all()

    async def update(
        self,
        transaction: PaymentTransaction,
    ) -> PaymentTransaction:
        await self.session.flush()
        await self.session.refresh(transaction)
        return transaction
