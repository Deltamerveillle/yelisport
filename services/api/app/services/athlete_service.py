"""Athlete management use cases."""

import uuid

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.athlete import Athlete
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.country_repository import CountryRepository
from app.schemas.athlete import AthleteCreate, AthleteUpdate


class AthleteService:
    def __init__(
        self,
        repository: AthleteRepository,
        country_repository: CountryRepository | None = None,
    ) -> None:
        self.repository = repository
        self.country_repository = country_repository

    async def _validate_residence_country(
        self,
        country_id: uuid.UUID | None,
    ) -> None:
        if country_id is None:
            return

        if self.country_repository is None:
            raise RuntimeError(
                "CountryRepository is required to validate residence_country_id"
            )

        country = await self.country_repository.get_by_id(country_id)

        if country is None or not country.is_active:
            raise NotFoundError(
                "Residence country not found or inactive"
            )

    async def create_athlete(
        self,
        data: AthleteCreate,
        current_user_id: uuid.UUID,
    ) -> Athlete:
        """Create a new athlete owned by the authenticated user."""
        existing = await self.repository.get_by_user_and_sport(
            current_user_id,
            data.sport_id,
        )
        if existing is not None:
            raise ConflictError("Athlete profile already exists for this sport")

        await self._validate_residence_country(
            data.residence_country_id,
        )

        athlete = Athlete(
            user_id=current_user_id,
            sport_id=data.sport_id,
            first_name=data.first_name,
            last_name=data.last_name,
            nationality=data.nationality,
            country=data.country,
            residence_country_id=data.residence_country_id,
            city=data.city,
            biography=data.biography,
        )
        return await self.repository.create(athlete)

    async def get_athlete(self, athlete_id: uuid.UUID) -> Athlete:
        """Get an athlete by ID."""
        athlete = await self.repository.get_by_id(athlete_id)
        if athlete is None:
            raise NotFoundError("Athlete not found")
        return athlete

    async def list_athletes(self) -> list[Athlete]:
        """List all athletes."""
        return await self.repository.list_all()

    async def list_user_athletes(self, user_id: uuid.UUID) -> list[Athlete]:
        """List all athletes for a specific user."""
        return await self.repository.get_by_user_id(user_id)

    async def list_sport_athletes(self, sport_id: uuid.UUID) -> list[Athlete]:
        """List all athletes for a specific sport."""
        return await self.repository.get_by_sport_id(sport_id)

    async def _get_owned_athlete(
        self,
        athlete_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> Athlete:
        athlete = await self.get_athlete(athlete_id)
        if athlete.user_id != current_user_id:
            raise ForbiddenError("You do not have permission to modify this athlete")
        return athlete

    async def update_athlete(
        self,
        athlete_id: uuid.UUID,
        data: AthleteUpdate,
        current_user_id: uuid.UUID,
    ) -> Athlete:
        """Update an athlete owned by the authenticated user."""
        athlete = await self._get_owned_athlete(athlete_id, current_user_id)

        updates = data.model_dump(exclude_unset=True)

        if "residence_country_id" in updates:
            await self._validate_residence_country(
                updates["residence_country_id"],
            )

        for field, value in updates.items():
            setattr(athlete, field, value)

        return await self.repository.update(athlete)

    async def delete_athlete(
        self,
        athlete_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> bool:
        """Delete an athlete owned by the authenticated user."""
        await self._get_owned_athlete(athlete_id, current_user_id)
        return await self.repository.delete(athlete_id)
