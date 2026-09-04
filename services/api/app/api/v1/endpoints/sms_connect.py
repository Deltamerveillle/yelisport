"""SMS Connect API."""

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_current_user,
)
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.schemas.sms_connect import (
    InterestStatus,
    SMSConnectInterestCreate,
    SMSConnectInterestEventResponse,
    SMSConnectInterestResponse,
    SMSConnectTransitionRequest,
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
        requester_user_id=uuid.UUID(
            str(current_user.id)
        ),
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


@router.get(
    "/athlete/inbox",
    response_model=list[
        SMSConnectInterestResponse
    ],
)
async def athlete_inbox(
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
    """List interests formally delivered to this athlete."""

    return await SMSConnectService(
        session
    ).list_athlete_inbox(
        uuid.UUID(str(current_user.id))
    )


@router.get(
    "/admin/interests",
    response_model=list[
        SMSConnectInterestResponse
    ],
)
async def admin_list_interests(
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    current_user: Annotated[
        AuthUser,
        Depends(get_current_user),
    ],
    interest_status: InterestStatus | None = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 100,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> Sequence[
    SMSConnectInterestResponse
]:
    """Internal SMS review queue."""

    return await SMSConnectService(
        session
    ).list_admin_interests(
        admin_user_id=uuid.UUID(
            str(current_user.id)
        ),
        interest_status=interest_status,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/admin/interests/{interest_id}/status",
    response_model=SMSConnectInterestResponse,
)
async def admin_transition_interest(
    interest_id: uuid.UUID,
    data: SMSConnectTransitionRequest,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    current_user: Annotated[
        AuthUser,
        Depends(get_current_user),
    ],
) -> SMSConnectInterestResponse:
    """Apply one controlled SMS Connect status transition."""

    return await SMSConnectService(
        session
    ).transition_interest(
        interest_id=interest_id,
        admin_user_id=uuid.UUID(
            str(current_user.id)
        ),
        data=data,
    )


@router.get(
    "/admin/interests/{interest_id}/events",
    response_model=list[
        SMSConnectInterestEventResponse
    ],
)
async def admin_interest_events(
    interest_id: uuid.UUID,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    current_user: Annotated[
        AuthUser,
        Depends(get_current_user),
    ],
) -> Sequence[
    SMSConnectInterestEventResponse
]:
    """Return immutable administrative transition history."""

    return await SMSConnectService(
        session
    ).list_interest_events(
        interest_id=interest_id,
        admin_user_id=uuid.UUID(
            str(current_user.id)
        ),
    )
