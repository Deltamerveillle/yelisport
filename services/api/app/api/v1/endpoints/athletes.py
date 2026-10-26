"""Athlete management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.core.exceptions import ForbiddenError
from app.db.session import get_db_session
from app.repositories.athlete_country_eligibility_repository import (
    AthleteCountryEligibilityRepository,
)
from app.repositories.athlete_performance_repository import AthletePerformanceRepository
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.country_repository import CountryRepository
from app.schemas.athlete import AthleteCreate, AthleteResponse, AthleteUpdate
from app.schemas.athlete_country_eligibility import AthleteCountryEligibilityCreate
from app.schemas.athlete_profile import AthleteProfileResponse
from app.services.athlete_country_eligibility_service import (
    AthleteCountryEligibilityService,
)
from app.services.athlete_profile_service import AthleteProfileService
from app.services.athlete_service import AthleteService
from app.services.subscription_service import SubscriptionService
from app.sms24.player_statistics_evidence import AthleteStatisticsEvidenceReader

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
    service = AthleteService(
        AthleteRepository(session),
        CountryRepository(session),
    )

    try:
        access = await SubscriptionService(session).get_access(
            _current_user_uuid(current_user)
        )
        if not access.has_premium_access:
            raise ForbiddenError("Abonnement actif requis pour créer un profil sportif")
        athlete = await service.create_athlete(
            payload,
            _current_user_uuid(current_user),
        )
        if payload.primary_country_id is not None:
            # Register the country/sport classification atomically with the athlete.
            # A declaration never implies verified eligibility or public visibility.
            await AthleteCountryEligibilityService(
                AthleteCountryEligibilityRepository(session),
                AthleteRepository(session),
                CountryRepository(session),
            ).declare_eligibility(
                athlete_id=athlete.id,
                data=AthleteCountryEligibilityCreate(
                    country_id=payload.primary_country_id,
                    is_primary=True,
                ),
                current_user_id=_current_user_uuid(current_user),
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
    service = AthleteService(
        AthleteRepository(session),
        CountryRepository(session),
    )
    athletes = await service.list_athletes()
    return [AthleteResponse.model_validate(athlete) for athlete in athletes]


@router.get("/me", response_model=list[AthleteResponse])
async def list_my_athlete_profiles(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AthleteResponse]:
    """Return only this authenticated user's sport profiles for enrolment resume."""
    service = AthleteService(
        AthleteRepository(session),
        CountryRepository(session),
    )
    athletes = await service.list_user_athletes(_current_user_uuid(current_user))
    return [AthleteResponse.model_validate(athlete) for athlete in athletes]


@router.get("/user/{user_id}", response_model=list[AthleteResponse])
async def list_user_athletes(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AthleteResponse]:
    """List athlete profiles belonging to a specific user."""
    del current_user
    service = AthleteService(
        AthleteRepository(session),
        CountryRepository(session),
    )
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
    service = AthleteService(
        AthleteRepository(session),
        CountryRepository(session),
    )
    athletes = await service.list_sport_athletes(sport_id)
    return [AthleteResponse.model_validate(athlete) for athlete in athletes]


@router.get("/{athlete_id}/profile", response_model=AthleteProfileResponse)
async def get_athlete_profile(
    athlete_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AthleteProfileResponse:
    """Get the read-only enriched SMS athlete profile."""
    del current_user
    service = AthleteProfileService(
        athlete_repository=AthleteRepository(session),
        performance_repository=AthletePerformanceRepository(session),
        statistics_reader=AthleteStatisticsEvidenceReader(session=session),
    )
    return await service.get_profile(athlete_id)


@router.get("/{athlete_id}", response_model=AthleteResponse)
async def get_athlete(
    athlete_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AthleteResponse:
    """Get a specific athlete profile."""
    del current_user
    service = AthleteService(
        AthleteRepository(session),
        CountryRepository(session),
    )
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
    service = AthleteService(
        AthleteRepository(session),
        CountryRepository(session),
    )

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
    service = AthleteService(
        AthleteRepository(session),
        CountryRepository(session),
    )

    try:
        await service.delete_athlete(
            athlete_id,
            _current_user_uuid(current_user),
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
