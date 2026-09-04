"""SMS Performance API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db_session
from app.schemas.athlete_performance import (
    AthletePerformanceCreate,
    AthletePerformanceResponse,
    AthletePerformanceUpdate,
)
from app.services.athlete_performance_service import (
    AthletePerformanceService,
)


router = APIRouter(
    tags=["SMS Performance"],
)


def _current_user_uuid(
    current_user: CurrentUser,
) -> uuid.UUID:
    return uuid.UUID(str(current_user.id))


def _service(
    session: AsyncSession,
) -> AthletePerformanceService:
    return AthletePerformanceService(session)


@router.post(
    "/athletes/{athlete_id}/performances",
    response_model=AthletePerformanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_athlete_performance(
    athlete_id: uuid.UUID,
    data: AthletePerformanceCreate,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Create a self-declared performance."""

    service = _service(session)

    try:
        performance = await service.create_performance(
            athlete_id,
            data,
            _current_user_uuid(current_user),
        )
        await session.commit()
        return performance
    except Exception:
        await session.rollback()
        raise


@router.get(
    "/athletes/{athlete_id}/performances",
    response_model=list[AthletePerformanceResponse],
)
async def list_athlete_performances(
    athlete_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """List performances belonging to an owned athlete."""

    return await _service(
        session
    ).list_athlete_performances(
        athlete_id,
        _current_user_uuid(current_user),
    )


@router.get(
    "/athletes/{athlete_id}/performances/{performance_id}",
    response_model=AthletePerformanceResponse,
)
async def get_athlete_performance(
    athlete_id: uuid.UUID,
    performance_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Get one performance belonging to an owned athlete."""

    return await _service(session).get_performance(
        athlete_id,
        performance_id,
        _current_user_uuid(current_user),
    )


@router.put(
    "/athletes/{athlete_id}/performances/{performance_id}",
    response_model=AthletePerformanceResponse,
)
async def update_athlete_performance(
    athlete_id: uuid.UUID,
    performance_id: uuid.UUID,
    data: AthletePerformanceUpdate,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Update one non-verified performance."""

    service = _service(session)

    try:
        performance = await service.update_performance(
            athlete_id,
            performance_id,
            data,
            _current_user_uuid(current_user),
        )
        await session.commit()
        return performance
    except Exception:
        await session.rollback()
        raise


@router.delete(
    "/athletes/{athlete_id}/performances/{performance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_athlete_performance(
    athlete_id: uuid.UUID,
    performance_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Delete one non-verified performance."""

    service = _service(session)

    try:
        await service.delete_performance(
            athlete_id,
            performance_id,
            _current_user_uuid(current_user),
        )
        await session.commit()
        return Response(
            status_code=status.HTTP_204_NO_CONTENT
        )
    except Exception:
        await session.rollback()
        raise
