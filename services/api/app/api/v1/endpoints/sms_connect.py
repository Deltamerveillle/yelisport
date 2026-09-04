"""SMS Connect API."""

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_current_user,
)
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.schemas.sms_connect import (
    SMSConnectInterestCreate,
    SMSConnectInterestResponse,
)
from app.services.sms_connect_service import (
    SMSConnectService,
)


router = APIRouter(
    prefix="/sms-connect",
    tags=["sms-connect"],
)


@router.post(
    "/athletes/{athlete_id}/interests",
    response_model=SMSConnectInterestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_interest(
    athlete_id: uuid.UUID,
    data: SMSConnectInterestCreate,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    current_user: Annotated[
        AuthUser,
        Depends(get_current_user),
    ],
) -> SMSConnectInterestResponse:
    """
    Submit professional interest through SMS.

    Athlete personal phone, email and WhatsApp
    information are never exposed.
    """

    return await SMSConnectService(
        session
    ).create_interest(
        athlete_id=athlete_id,
        requester_user_id=uuid.UUID(str(current_user.id)),
        data=data,
    )


@router.get(
    "/me/interests",
    response_model=list[
        SMSConnectInterestResponse
    ],
)
async def list_my_interests(
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    current_user: Annotated[
        AuthUser,
        Depends(get_current_user),
    ],
) -> Sequence[
    SMSConnectInterestResponse
]:
    """List professional interests sent by the user."""

    return await SMSConnectService(
        session
    ).list_my_interests(
        uuid.UUID(str(current_user.id))
    )
