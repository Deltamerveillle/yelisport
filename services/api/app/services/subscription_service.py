"""Service layer for SMS subscriptions and access rights."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription
from app.repositories.subscription_repository import (
    SubscriptionRepository,
)


class SubscriptionService:
    """Business rules for SMS subscriptions."""

    def __init__(self, session: AsyncSession) -> None:
        self.subscriptions = SubscriptionRepository(session)

    async def list_user_subscriptions(
        self,
        user_id: uuid.UUID,
    ) -> Sequence[Subscription]:
        """Return the authenticated user's subscription history."""

        return await self.subscriptions.list_by_user_id(user_id)

    async def get_current_subscription(
        self,
        user_id: uuid.UUID,
    ) -> Subscription | None:
        """Return a currently usable subscription, if any."""

        subscription = await self.subscriptions.get_current_for_user(
            user_id
        )

        if subscription is None:
            return None

        if (
            subscription.current_period_end is not None
            and subscription.current_period_end <= datetime.now(UTC)
        ):
            return None

        return subscription

    async def has_premium_access(
        self,
        user_id: uuid.UUID,
    ) -> bool:
        """Determine whether the user currently has premium SMS access."""

        subscription = await self.get_current_subscription(user_id)

        if subscription is None:
            return False

        return (
            subscription.status in {"active", "trialing"}
            and subscription.plan_code != "free"
        )
