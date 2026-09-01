"""SMS Passport endpoints."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db_session
from app.repositories.athlete_passport_repository import AthletePassportRepository
from app.repositories.athlete_repository import AthleteRepository
from app.schemas.athlete_passport import (
    AthletePassportCreate,
    AthletePassportResponse,
    AthletePassportUpdate,
)
from app.services.athlete_passport_service import AthletePassportService


router = APIRouter(
    prefix="/athletes/{athlete_id}/passport",
    tags=["SMS Passport"],
)


def _current_user_uuid(current_user: CurrentUser) -> uuid.UUID:
    return uuid.UUID(current_user.id)


def _service(session: AsyncSession) -> AthletePassportService:
    return AthletePassportService(
        passport_repository=AthletePassportRepository(session),
        athlete_repository=AthleteRepository(session),
    )


@router.post(
    "",
    response_model=AthletePassportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_passport(
    athlete_id: uuid.UUID,
    payload: AthletePassportCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> AthletePassportResponse:
    service = _service(session)

    try:
        passport = await service.create_passport(
            athlete_id=athlete_id,
            data=payload,
            current_user_id=_current_user_uuid(current_user),
        )
        await session.commit()
        return AthletePassportResponse.model_validate(passport)
    except Exception:
        await session.rollback()
        raise


@router.get(
    "",
    response_model=AthletePassportResponse,
)
async def get_passport(
    athlete_id: uuid.UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> AthletePassportResponse:
    service = _service(session)

    passport = await service.get_passport(
        athlete_id=athlete_id,
    )

    return AthletePassportResponse.model_validate(passport)


@router.put(
    "",
    response_model=AthletePassportResponse,
)
async def update_passport(
    athlete_id: uuid.UUID,
    payload: AthletePassportUpdate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> AthletePassportResponse:
    service = _service(session)

    try:
        passport = await service.update_passport(
            athlete_id=athlete_id,
            data=payload,
            current_user_id=_current_user_uuid(current_user),
        )
        await session.commit()
        return AthletePassportResponse.model_validate(passport)
    except Exception:
        await session.rollback()
        raise


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_passport(
    athlete_id: uuid.UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    service = _service(session)

    try:
        await service.delete_passport(
            athlete_id=athlete_id,
            current_user_id=_current_user_uuid(current_user),
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
