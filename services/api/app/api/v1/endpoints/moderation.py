"""SMS moderation API endpoints."""

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db_session
from app.schemas.discover_video import DiscoverVideoResponse
from app.schemas.moderation import (
    UserModerationAction,
    UserModerationResponse,
    DiscoverModerationDecision,
    ModerationAdminReportResponse,
    ModerationEventResponse,
    ModerationReportCreate,
    ModerationReportResponse,
    ModerationResourceType,
    ModerationStatus,
    ModerationTransitionRequest,
)
from app.services.moderation_service import (
    ModerationService,
)


router = APIRouter(
    prefix="/moderation",
    tags=["SMS Moderation"],
)


def _current_user_uuid(
    current_user: CurrentUser,
) -> uuid.UUID:
    return uuid.UUID(str(current_user.id))


def _service(
    session: AsyncSession,
) -> ModerationService:
    return ModerationService(session)


@router.post(
    "/reports",
    response_model=ModerationReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_moderation_report(
    data: ModerationReportCreate,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Submit a report about an SMS resource."""

    service = _service(session)

    try:
        report = await service.create_report(
            reporter_user_id=_current_user_uuid(
                current_user
            ),
            data=data,
        )
        await session.commit()
        return report
    except Exception:
        await session.rollback()
        raise


@router.get(
    "/me/reports",
    response_model=list[
        ModerationReportResponse
    ],
)
async def list_my_moderation_reports(
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
):
    """List reports created by the current user."""

    return await _service(
        session
    ).list_my_reports(
        reporter_user_id=_current_user_uuid(
            current_user
        ),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/admin/reports",
    response_model=list[
        ModerationAdminReportResponse
    ],
)
async def admin_list_moderation_reports(
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    report_status: ModerationStatus | None = Query(
        default=None,
        alias="status",
    ),
    resource_type: ModerationResourceType | None = Query(
        default=None,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
):
    """Administrative moderation queue."""

    return await _service(
        session
    ).list_admin_reports(
        admin_user_id=_current_user_uuid(
            current_user
        ),
        status=report_status,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/admin/reports/{report_id}/status",
    response_model=ModerationAdminReportResponse,
)
async def admin_transition_moderation_report(
    report_id: uuid.UUID,
    data: ModerationTransitionRequest,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Move a moderation report through its review lifecycle."""

    service = _service(session)

    try:
        report = await service.transition_report(
            report_id=report_id,
            admin_user_id=_current_user_uuid(
                current_user
            ),
            data=data,
        )
        await session.commit()
        return report
    except Exception:
        await session.rollback()
        raise


@router.get(
    "/admin/reports/{report_id}/events",
    response_model=list[
        ModerationEventResponse
    ],
)
async def admin_list_moderation_events(
    report_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Return immutable moderation audit history."""

    return await _service(
        session
    ).list_report_events(
        report_id=report_id,
        admin_user_id=_current_user_uuid(
            current_user
        ),
    )



@router.patch(
    "/admin/reports/{report_id}/discover-decision",
    response_model=DiscoverVideoResponse,
)
async def decide_discover_video(
    report_id: uuid.UUID,
    data: DiscoverModerationDecision,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Approve or reject a Discover video under review."""

    service = _service(session)

    try:
        video = await service.decide_discover_video(
            report_id=report_id,
            admin_user_id=_current_user_uuid(
                current_user
            ),
            data=data,
        )
        await session.commit()
        return video
    except Exception:
        await session.rollback()
        raise



@router.patch(
    "/admin/reports/{report_id}/user-action",
    response_model=UserModerationResponse,
)
async def moderate_user(
    report_id: uuid.UUID,
    data: UserModerationAction,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Suspend or reactivate a user from a moderation case."""

    service = _service(session)

    try:
        user = await service.moderate_user(
            report_id=report_id,
            admin_user_id=_current_user_uuid(
                current_user
            ),
            data=data,
        )
        await session.commit()
        return user
    except Exception:
        await session.rollback()
        raise
