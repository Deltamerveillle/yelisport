"""Repository for SMS subscriptions."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription


class SubscriptionRepository:
    """Database operations for SMS subscriptions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        subscription: Subscription,
    ) -> Subscription:
        self.session.add(subscription)
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def get_by_id(
        self,
        subscription_id: uuid.UUID,
    ) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.id == subscription_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user_id(
        self,
        user_id: uuid.UUID,
    ) -> Sequence[Subscription]:
        result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id
            )
            .order_by(
                Subscription.created_at.desc()
            )
        )
        return result.scalars().all()

    async def get_current_for_user(
        self,
        user_id: uuid.UUID,
    ) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_(
                    (
                        "active",
                        "trialing",
                    )
                ),
            )
            .order_by(
                Subscription.created_at.desc()
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        subscription: Subscription,
    ) -> Subscription:
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription
