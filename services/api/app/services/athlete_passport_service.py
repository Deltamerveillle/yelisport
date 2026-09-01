"""SMS Passport use cases."""

import uuid

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.athlete import Athlete
from app.models.athlete_passport import AthletePassport
from app.repositories.athlete_passport_repository import AthletePassportRepository
from app.repositories.athlete_repository import AthleteRepository
from app.schemas.athlete_passport import (
    AthletePassportCreate,
    AthletePassportUpdate,
)


class AthletePassportService:
    def __init__(
        self,
        passport_repository: AthletePassportRepository,
        athlete_repository: AthleteRepository,
    ) -> None:
        self.passport_repository = passport_repository
        self.athlete_repository = athlete_repository

    async def _get_athlete(
        self,
        athlete_id: uuid.UUID,
    ) -> Athlete:
        athlete = await self.athlete_repository.get_by_id(athlete_id)

        if athlete is None:
            raise NotFoundError("Athlete not found")

        return athlete

    async def _get_owned_athlete(
        self,
        athlete_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> Athlete:
        athlete = await self._get_athlete(athlete_id)

        if athlete.user_id != current_user_id:
            raise ForbiddenError(
                "You do not have permission to modify this athlete passport"
            )

        return athlete

    async def create_passport(
        self,
        athlete_id: uuid.UUID,
        data: AthletePassportCreate,
        current_user_id: uuid.UUID,
    ) -> AthletePassport:
        await self._get_owned_athlete(
            athlete_id,
            current_user_id,
        )

        existing = await self.passport_repository.get_by_athlete_id(
            athlete_id
        )

        if existing is not None:
            raise ConflictError(
                "SMS Passport already exists for this athlete"
            )

        passport = AthletePassport(
            athlete_id=athlete_id,
            discipline=data.discipline,
            category=data.category,
            position=data.position,
            club_name=data.club_name,
            team_name=data.team_name,
            height_cm=data.height_cm,
            weight_kg=data.weight_kg,
            dominant_side=data.dominant_side,
            available_for_opportunities=data.available_for_opportunities,
            sporting_summary=data.sporting_summary,
        )

        return await self.passport_repository.create(passport)

    async def get_passport(
        self,
        athlete_id: uuid.UUID,
    ) -> AthletePassport:
        await self._get_athlete(athlete_id)

        passport = await self.passport_repository.get_by_athlete_id(
            athlete_id
        )

        if passport is None:
            raise NotFoundError("SMS Passport not found")

        return passport

    async def update_passport(
        self,
        athlete_id: uuid.UUID,
        data: AthletePassportUpdate,
        current_user_id: uuid.UUID,
    ) -> AthletePassport:
        await self._get_owned_athlete(
            athlete_id,
            current_user_id,
        )

        passport = await self.passport_repository.get_by_athlete_id(
            athlete_id
        )

        if passport is None:
            raise NotFoundError("SMS Passport not found")

        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(passport, field, value)

        return await self.passport_repository.update(passport)

    async def delete_passport(
        self,
        athlete_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> bool:
        await self._get_owned_athlete(
            athlete_id,
            current_user_id,
        )

        passport = await self.passport_repository.get_by_athlete_id(
            athlete_id
        )

        if passport is None:
            raise NotFoundError("SMS Passport not found")

        return await self.passport_repository.delete(passport.id)
