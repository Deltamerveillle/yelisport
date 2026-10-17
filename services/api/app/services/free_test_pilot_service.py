"""One-time internal pilot subscriptions, entirely independent of payment confirmation."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ApplicationError, ConflictError
from app.models.subscription import Subscription
from app.repositories.subscription_repository import SubscriptionRepository

TRIAL_PROVIDER = "internal_free_test_pilot"


class FreeTestPilotService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.subscriptions = SubscriptionRepository(session)

    async def activate(self, user_id: uuid.UUID) -> Subscription:
        settings = self.settings
        if (
            settings.app_env not in {"development", "test", "staging"}
            or not settings.sms_free_test_pilot_enabled
        ):
            raise ApplicationError("Pilote indisponible", code="pilot_disabled", status_code=404)
        plan = next(
            (
                p
                for p in settings.sms_commercial_plans
                if p.plan_code == settings.sms_free_test_pilot_plan_code
            ),
            None,
        )
        if plan is None or plan.entitlements.priority_visibility:
            raise ApplicationError(
                "Configuration du pilote indisponible", code="pilot_unavailable", status_code=503
            )

        # Also serializes against existing payment readers/writers without changing them.
        # Acquire before any subscription read; released by the caller's commit/rollback.
        await self.session.execute(text("LOCK TABLE subscriptions IN ACCESS EXCLUSIVE MODE"))
        history = await self.subscriptions.list_by_user_id(user_id)
        now = datetime.now(UTC)
        previous = next((s for s in history if s.provider == TRIAL_PROVIDER), None)
        if previous is not None:
            if (
                previous.status == "trialing"
                and previous.current_period_end is not None
                and previous.current_period_end > now
            ):
                return previous
            raise ConflictError("Essai déjà utilisé", code="trial_already_used")

        current = [s for s in history if s.status in {"active", "trialing"}]
        if any(s.current_period_end is None or s.current_period_end > now for s in current):
            raise ConflictError("Abonnement déjà en cours", code="subscription_already_current")
        for subscription in current:
            subscription.status = "replaced"
        return await self.subscriptions.create(
            Subscription(
                user_id=user_id,
                plan_code=plan.plan_code,
                status="trialing",
                provider=TRIAL_PROVIDER,
                current_period_start=now,
                current_period_end=now + timedelta(days=settings.sms_free_test_pilot_duration_days),
            )
        )
