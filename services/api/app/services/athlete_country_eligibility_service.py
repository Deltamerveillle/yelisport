"""SMS Nations athlete country eligibility use cases."""

import uuid

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.athlete_country_eligibility import AthleteCountryEligibility
from app.repositories.athlete_country_eligibility_repository import (
    AthleteCountryEligibilityRepository,
)
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.country_repository import CountryRepository
from app.schemas.athlete_country_eligibility import (
    AthleteCountryEligibilityCreate,
)


class AthleteCountryEligibilityService:
    def __init__(
        self,
        eligibility_repository: AthleteCountryEligibilityRepository,
        athlete_repository: AthleteRepository,
        country_repository: CountryRepository,
    ) -> None:
        self.eligibility_repository = eligibility_repository
        self.athlete_repository = athlete_repository
        self.country_repository = country_repository

    async def _get_owned_athlete_locked(
        self,
        athlete_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ):
        athlete = await self.athlete_repository.get_by_id(
            athlete_id,
            for_update=True,
        )

        if athlete is None:
            raise NotFoundError("Athlete not found")

        if athlete.user_id != current_user_id:
            raise ForbiddenError(
                "You do not have permission to manage this athlete eligibility"
            )

        return athlete

    async def _validate_country(
        self,
        country_id: uuid.UUID,
    ) -> None:
        country = await self.country_repository.get_by_id(country_id)

        if country is None or not country.is_active:
            raise NotFoundError("Country not found or inactive")

    async def declare_eligibility(
        self,
        *,
        athlete_id: uuid.UUID,
        data: AthleteCountryEligibilityCreate,
        current_user_id: uuid.UUID,
    ) -> AthleteCountryEligibility:
        await self._get_owned_athlete_locked(
            athlete_id,
            current_user_id,
        )

        await self._validate_country(data.country_id)

        existing = await self.eligibility_repository.get_by_athlete_and_country(
            athlete_id=athlete_id,
            country_id=data.country_id,
        )

        if existing is not None:
            raise ConflictError(
                "Country eligibility already declared for this athlete"
            )

        existing_eligibilities = (
            await self.eligibility_repository.list_by_athlete(
                athlete_id
            )
        )

        is_primary = data.is_primary or not existing_eligibilities

        if is_primary and existing_eligibilities:
            await self.eligibility_repository.clear_primary_for_athlete(
                athlete_id
            )

        return await self.eligibility_repository.create(
            athlete_id=athlete_id,
            country_id=data.country_id,
            is_primary=is_primary,
        )

    async def list_eligibilities(
        self,
        athlete_id: uuid.UUID,
    ) -> list[AthleteCountryEligibility]:
        athlete = await self.athlete_repository.get_by_id(athlete_id)

        if athlete is None:
            raise NotFoundError("Athlete not found")

        return await self.eligibility_repository.list_by_athlete(
            athlete_id
        )
