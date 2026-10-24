"""Authenticated notification inbox."""

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_current_user,
)
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.schemas.notification import (
    NotificationResponse,
    NotificationUnreadCountResponse,
)
from app.services.notification_service import (
    NotificationService,
)

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)


@router.get(
    "/me",
    response_model=list[NotificationResponse],
)
async def list_my_notifications(
    unread_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    return await NotificationService(
        session
    ).list_my_notifications(
        uuid.UUID(str(current_user.id)),
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/me/unread-count",
    response_model=(
        NotificationUnreadCountResponse
    ),
)
async def unread_count(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    count = await NotificationService(
        session
    ).unread_count(
        uuid.UUID(str(current_user.id))
    )

    return NotificationUnreadCountResponse(
        unread_count=count
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    return await NotificationService(
        session
    ).mark_read(
        notification_id=notification_id,
        user_id=uuid.UUID(
            str(current_user.id)
        ),
    )
