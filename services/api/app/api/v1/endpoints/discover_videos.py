"""SMS Discover API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db_session
from app.schemas.discover_video import (
    DiscoverVideoCreate,
    DiscoverVideoResponse,
    DiscoverVideoUpdate,
)
from app.services.discover_video_service import DiscoverVideoService


router = APIRouter(
    tags=["SMS Discover"],
)


def _current_user_uuid(current_user: CurrentUser) -> uuid.UUID:
    return uuid.UUID(str(current_user.id))


def _service(session: AsyncSession) -> DiscoverVideoService:
    return DiscoverVideoService(session)


@router.get(
    "/discover",
    response_model=list[DiscoverVideoResponse],
)
async def list_public_discover(
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Public SMS Discover feed."""

    return await _service(session).list_public_discover(
        limit=limit,
        offset=offset,
    )


@router.post(
    "/athletes/{athlete_id}/discover-videos",
    response_model=DiscoverVideoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_discover_video(
    athlete_id: uuid.UUID,
    data: DiscoverVideoCreate,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Create a Discover video for an owned athlete."""

    service = _service(session)

    try:
        video = await service.create_video(
            athlete_id,
            data,
            _current_user_uuid(current_user),
        )
        await session.commit()
        return video
    except Exception:
        await session.rollback()
        raise


@router.get(
    "/athletes/{athlete_id}/discover-videos",
    response_model=list[DiscoverVideoResponse],
)
async def list_athlete_discover_videos(
    athlete_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """List all Discover videos for an owned athlete."""

    return await _service(session).list_athlete_videos(
        athlete_id,
        _current_user_uuid(current_user),
    )


@router.get(
    "/athletes/{athlete_id}/discover-videos/{video_id}",
    response_model=DiscoverVideoResponse,
)
async def get_discover_video(
    athlete_id: uuid.UUID,
    video_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Get one Discover video for an owned athlete."""

    return await _service(session).get_video(
        athlete_id,
        video_id,
        _current_user_uuid(current_user),
    )


@router.put(
    "/athletes/{athlete_id}/discover-videos/{video_id}",
    response_model=DiscoverVideoResponse,
)
async def update_discover_video(
    athlete_id: uuid.UUID,
    video_id: uuid.UUID,
    data: DiscoverVideoUpdate,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Update one Discover video for an owned athlete."""

    service = _service(session)

    try:
        video = await service.update_video(
            athlete_id,
            video_id,
            data,
            _current_user_uuid(current_user),
        )
        await session.commit()
        return video
    except Exception:
        await session.rollback()
        raise


@router.delete(
    "/athletes/{athlete_id}/discover-videos/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_discover_video(
    athlete_id: uuid.UUID,
    video_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Delete one Discover video for an owned athlete."""

    service = _service(session)

    try:
        await service.delete_video(
            athlete_id,
            video_id,
            _current_user_uuid(current_user),
        )
        await session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception:
        await session.rollback()
        raise
