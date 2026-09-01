"""Authenticated SMS subscription endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db_session
from app.schemas.subscription import (
    SubscriptionAccessResponse,
    SubscriptionResponse,
)
from app.services.subscription_service import SubscriptionService


router = APIRouter()


@router.get(
    "/me",
    response_model=SubscriptionResponse | None,
)
async def get_my_current_subscription(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SubscriptionResponse | None:
    """Return the authenticated user's current subscription."""

    service = SubscriptionService(session)

    subscription = await service.get_current_subscription(
        current_user.id
    )

    if subscription is None:
        return None

    return SubscriptionResponse.model_validate(subscription)


@router.get(
    "/me/history",
    response_model=list[SubscriptionResponse],
)
async def get_my_subscription_history(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[SubscriptionResponse]:
    """Return the authenticated user's subscription history."""

    service = SubscriptionService(session)

    subscriptions = await service.list_user_subscriptions(
        current_user.id
    )

    return [
        SubscriptionResponse.model_validate(subscription)
        for subscription in subscriptions
    ]


@router.get(
    "/me/access",
    response_model=SubscriptionAccessResponse,
)
async def get_my_subscription_access(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SubscriptionAccessResponse:
    """Return the authenticated user's current SMS access rights."""

    service = SubscriptionService(session)

    subscription = await service.get_current_subscription(
        current_user.id
    )

    if subscription is None:
        return SubscriptionAccessResponse(
            has_premium_access=False,
            plan_code="free",
            status="inactive",
            current_period_end=None,
        )

    has_premium_access = await service.has_premium_access(
        current_user.id
    )

    return SubscriptionAccessResponse(
        has_premium_access=has_premium_access,
        plan_code=subscription.plan_code,
        status=subscription.status,
        current_period_end=subscription.current_period_end,
    )
