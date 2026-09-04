"""Business rules for SMS athlete performances."""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.athlete_performance import AthletePerformance
from app.repositories.athlete_performance_repository import (
    AthletePerformanceRepository,
)
from app.repositories.athlete_repository import AthleteRepository
from app.schemas.athlete_performance import (
    AthletePerformanceCreate,
    AthletePerformanceUpdate,
)


class AthletePerformanceService:
    """Business rules for SMS Performance."""

    def __init__(self, session: AsyncSession) -> None:
        self.athletes = AthleteRepository(session)
        self.performances = AthletePerformanceRepository(session)

    async def _get_athlete(
        self,
        athlete_id: uuid.UUID,
    ):
        athlete = await self.athletes.get_by_id(athlete_id)

        if athlete is None:
            raise NotFoundError("Athlete not found")

        return athlete

    async def _get_owned_athlete(
        self,
        athlete_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ):
        athlete = await self._get_athlete(athlete_id)

        if athlete.user_id != current_user_id:
            raise ForbiddenError(
                "You do not have permission to manage "
                "performances for this athlete"
            )

        return athlete

    async def _get_performance(
        self,
        performance_id: uuid.UUID,
    ) -> AthletePerformance:
        performance = await self.performances.get_by_id(
            performance_id
        )

        if performance is None:
            raise NotFoundError("Athlete performance not found")

        return performance

    async def _get_owned_performance(
        self,
        athlete_id: uuid.UUID,
        performance_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> AthletePerformance:
        await self._get_owned_athlete(
            athlete_id,
            current_user_id,
        )

        performance = await self._get_performance(
            performance_id
        )

        if performance.athlete_id != athlete_id:
            raise NotFoundError("Athlete performance not found")

        return performance

    async def create_performance(
        self,
        athlete_id: uuid.UUID,
        data: AthletePerformanceCreate,
        current_user_id: uuid.UUID,
    ) -> AthletePerformance:
        athlete = await self._get_owned_athlete(
            athlete_id,
            current_user_id,
        )

        performance = AthletePerformance(
            athlete_id=athlete.id,
            sport_id=athlete.sport_id,
            discipline=data.discipline,
            performance_type=data.performance_type,
            competition_name=data.competition_name,
            season=data.season,
            performance_date=data.performance_date,
            metrics=data.metrics,
            summary=data.summary,
            verification_status="declared",
            source_name=data.source_name,
            source_url=(
                str(data.source_url)
                if data.source_url is not None
                else None
            ),
        )

        return await self.performances.create(
            performance
        )

    async def list_athlete_performances(
        self,
        athlete_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> Sequence[AthletePerformance]:
        await self._get_owned_athlete(
            athlete_id,
            current_user_id,
        )

        return await self.performances.list_by_athlete_id(
            athlete_id
        )

    async def get_performance(
        self,
        athlete_id: uuid.UUID,
        performance_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> AthletePerformance:
        return await self._get_owned_performance(
            athlete_id,
            performance_id,
            current_user_id,
        )

    async def update_performance(
        self,
        athlete_id: uuid.UUID,
        performance_id: uuid.UUID,
        data: AthletePerformanceUpdate,
        current_user_id: uuid.UUID,
    ) -> AthletePerformance:
        performance = await self._get_owned_performance(
            athlete_id,
            performance_id,
            current_user_id,
        )

        # Once SMS Proof has verified a performance, the athlete
        # must not silently rewrite the evidence behind it.
        if performance.verification_status == "verified":
            raise ForbiddenError(
                "Verified performances cannot be edited "
                "by the athlete"
            )

        updates = data.model_dump(
            exclude_unset=True
        )

        if "source_url" in updates:
            value = updates["source_url"]
            updates["source_url"] = (
                str(value)
                if value is not None
                else None
            )

        for field, value in updates.items():
            setattr(
                performance,
                field,
                value,
            )

        # Any substantive athlete edit invalidates previous
        # documentary review. The evidence must be reviewed again.
        #
        # Verified performances are already blocked above.
        if updates:
            performance.verification_status = "declared"

        return await self.performances.update(
            performance
        )

    async def delete_performance(
        self,
        athlete_id: uuid.UUID,
        performance_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> None:
        performance = await self._get_owned_performance(
            athlete_id,
            performance_id,
            current_user_id,
        )

        if performance.verification_status == "verified":
            raise ForbiddenError(
                "Verified performances cannot be deleted "
                "by the athlete"
            )

        await self.performances.delete(
            performance
        )
