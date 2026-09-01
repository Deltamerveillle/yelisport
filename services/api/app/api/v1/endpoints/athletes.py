"""Athlete management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db_session
from app.repositories.athlete_repository import AthleteRepository
from app.schemas.athlete import AthleteCreate, AthleteResponse, AthleteUpdate
from app.services.athlete_service import AthleteService

router = APIRouter(prefix="/athletes", tags=["athletes"])


def _current_user_uuid(current_user: CurrentUser) -> uuid.UUID:
    """Return the authenticated user's ID as a UUID."""
    return uuid.UUID(current_user.id)


@router.post("", response_model=AthleteResponse, status_code=status.HTTP_201_CREATED)
async def create_athlete(
    payload: AthleteCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AthleteResponse:
    """Create an athlete profile owned by the authenticated user."""
    service = AthleteService(AthleteRepository(session))

    try:
        athlete = await service.create_athlete(
            payload,
            _current_user_uuid(current_user),
        )
        await session.commit()
        return AthleteResponse.model_validate(athlete)
    except Exception:
        await session.rollback()
        raise


@router.get("", response_model=list[AthleteResponse])
async def list_athletes(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AthleteResponse]:
    """List all athletes."""
    del current_user
    service = AthleteService(AthleteRepository(session))
    athletes = await service.list_athletes()
    return [AthleteResponse.model_validate(athlete) for athlete in athletes]


@router.get("/user/{user_id}", response_model=list[AthleteResponse])
async def list_user_athletes(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AthleteResponse]:
    """List athlete profiles belonging to a specific user."""
    del current_user
    service = AthleteService(AthleteRepository(session))
    athletes = await service.list_user_athletes(user_id)
    return [AthleteResponse.model_validate(athlete) for athlete in athletes]


@router.get("/sport/{sport_id}", response_model=list[AthleteResponse])
async def list_sport_athletes(
    sport_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AthleteResponse]:
    """List athlete profiles for a specific sport."""
    del current_user
    service = AthleteService(AthleteRepository(session))
    athletes = await service.list_sport_athletes(sport_id)
    return [AthleteResponse.model_validate(athlete) for athlete in athletes]


@router.get("/{athlete_id}", response_model=AthleteResponse)
async def get_athlete(
    athlete_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AthleteResponse:
    """Get a specific athlete profile."""
    del current_user
    service = AthleteService(AthleteRepository(session))
    athlete = await service.get_athlete(athlete_id)
    return AthleteResponse.model_validate(athlete)


@router.put("/{athlete_id}", response_model=AthleteResponse)
async def update_athlete(
    athlete_id: uuid.UUID,
    payload: AthleteUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AthleteResponse:
    """Update an athlete profile owned by the authenticated user."""
    service = AthleteService(AthleteRepository(session))

    try:
        athlete = await service.update_athlete(
            athlete_id,
            payload,
            _current_user_uuid(current_user),
        )
        await session.commit()
        return AthleteResponse.model_validate(athlete)
    except Exception:
        await session.rollback()
        raise


@router.delete("/{athlete_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_athlete(
    athlete_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete an athlete profile owned by the authenticated user."""
    service = AthleteService(AthleteRepository(session))

    try:
        await service.delete_athlete(
            athlete_id,
            _current_user_uuid(current_user),
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
