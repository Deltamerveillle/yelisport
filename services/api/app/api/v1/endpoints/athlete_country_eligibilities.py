"""SMS Nations athlete country eligibility endpoints."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.repositories.athlete_country_eligibility_repository import (
    AthleteCountryEligibilityRepository,
)
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.country_repository import CountryRepository
from app.schemas.athlete_country_eligibility import (
    AthleteCountryEligibilityCreate,
    AthleteCountryEligibilityResponse,
)
from app.schemas.auth import AuthUser
from app.services.athlete_country_eligibility_service import (
    AthleteCountryEligibilityService,
)

router = APIRouter(
    prefix="/athletes/{athlete_id}/eligibilities",
    tags=["SMS Nations"],
)


@router.post(
    "",
    response_model=AthleteCountryEligibilityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def declare_country_eligibility(
    athlete_id: uuid.UUID,
    data: AthleteCountryEligibilityCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = AthleteCountryEligibilityService(
        AthleteCountryEligibilityRepository(session),
        AthleteRepository(session),
        CountryRepository(session),
    )

    try:
        eligibility = await service.declare_eligibility(
            athlete_id=athlete_id,
            data=data,
            current_user_id=uuid.UUID(str(current_user.id)),
        )
        await session.commit()
        return eligibility
    except Exception:
        await session.rollback()
        raise


@router.get(
    "",
    response_model=list[AthleteCountryEligibilityResponse],
)
async def list_country_eligibilities(
    athlete_id: uuid.UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = AthleteCountryEligibilityService(
        AthleteCountryEligibilityRepository(session),
        AthleteRepository(session),
        CountryRepository(session),
    )

    return await service.list_eligibilities(athlete_id)
