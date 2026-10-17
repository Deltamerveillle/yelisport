"""Authenticated SMS subscription endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.subscription import (
    SubscriptionAccessResponse,
    SubscriptionResponse,
)
from app.services.free_test_pilot_service import FreeTestPilotService
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

    subscription = await service.get_current_subscription(current_user.id)

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

    subscriptions = await service.list_user_subscriptions(current_user.id)

    return [SubscriptionResponse.model_validate(subscription) for subscription in subscriptions]


@router.get(
    "/me/access",
    response_model=SubscriptionAccessResponse,
)
async def get_my_subscription_access(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SubscriptionAccessResponse:
    """Return the authenticated user's current SMS access rights."""

    return await SubscriptionService(session).get_access(current_user.id)


@router.post("/me/trial", response_model=SubscriptionResponse)
async def activate_my_trial(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SubscriptionResponse:
    """Activate the one-time internal V1 pilot; this is not a payment."""
    try:
        subscription = await FreeTestPilotService(session, settings).activate(
            uuid.UUID(str(current_user.id))
        )
        response = SubscriptionResponse.model_validate(subscription)
        await session.commit()
        return response
    except Exception:
        await session.rollback()
        raise
