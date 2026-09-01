"""Repository for SMS payment transactions."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_transaction import PaymentTransaction


class PaymentTransactionRepository:
    """Database operations for SMS payment transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
            select(PaymentTransaction).where(
                PaymentTransaction.id == transaction_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_reference(
        self,
        reference: str,
    ) -> PaymentTransaction | None:
        result = await self.session.execute(
            select(PaymentTransaction).where(
                PaymentTransaction.reference == reference
            )
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
                PaymentTransaction.provider_transaction_id
                == provider_transaction_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user_id(
        self,
        user_id: uuid.UUID,
    ) -> Sequence[PaymentTransaction]:
        result = await self.session.execute(
            select(PaymentTransaction)
            .where(
                PaymentTransaction.user_id == user_id
            )
            .order_by(
                PaymentTransaction.created_at.desc()
            )
        )
        return result.scalars().all()

    async def update(
        self,
        transaction: PaymentTransaction,
    ) -> PaymentTransaction:
        await self.session.flush()
        await self.session.refresh(transaction)
        return transaction
