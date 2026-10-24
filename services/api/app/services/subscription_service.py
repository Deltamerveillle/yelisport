"""Service layer for SMS subscriptions and access rights."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.subscription import Subscription
from app.repositories.subscription_repository import (
    SubscriptionRepository,
)
from app.schemas.entitlements import CommercialEntitlements
from app.schemas.subscription import SubscriptionAccessResponse


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

        subscription = await self.subscriptions.get_current_for_user(user_id)

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

        return self._legacy_premium(subscription)

    @staticmethod
    def _legacy_premium(subscription: Subscription | None) -> bool:
        return (
            subscription is not None
            and subscription.status in {"active", "trialing"}
            and subscription.plan_code != "free"
        )

    async def get_access(self, user_id: uuid.UUID) -> SubscriptionAccessResponse:
        """Resolve explicit capabilities from one subscription read and server catalogue.

        Legacy premium is compatibility information, not an entitlement fallback.
        Plan availability controls new purchases, not access for existing subscribers.
        """
        subscription = await self.get_current_subscription(user_id)
        premium = self._legacy_premium(subscription)
        entitlements = CommercialEntitlements()
        if premium and subscription is not None:
            plan = next(
                (
                    plan
                    for plan in get_settings().sms_commercial_plans
                    if plan.plan_code == subscription.plan_code
                ),
                None,
            )
            if plan is not None:
                entitlements = plan.entitlements
        return SubscriptionAccessResponse(
            has_premium_access=premium,
            plan_code=subscription.plan_code if subscription is not None else "free",
            status=subscription.status if subscription is not None else "inactive",
            current_period_end=(
                subscription.current_period_end if subscription is not None else None
            ),
            entitlements=entitlements,
        )
