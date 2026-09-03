"""Repository for SMS Nations athlete country eligibility."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_country_eligibility import (
    AthleteCountryEligibility,
)


class AthleteCountryEligibilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        athlete_id: uuid.UUID,
        country_id: uuid.UUID,
        is_primary: bool = False,
    ) -> AthleteCountryEligibility:
        eligibility = AthleteCountryEligibility(
            athlete_id=athlete_id,
            country_id=country_id,
            status="declared",
            is_primary=is_primary,
        )

        self.session.add(eligibility)
        await self.session.flush()
        await self.session.refresh(eligibility)
        return eligibility

    async def get_by_athlete_and_country(
        self,
        *,
        athlete_id: uuid.UUID,
        country_id: uuid.UUID,
    ) -> AthleteCountryEligibility | None:
        return await self.session.scalar(
            select(AthleteCountryEligibility).where(
                AthleteCountryEligibility.athlete_id == athlete_id,
                AthleteCountryEligibility.country_id == country_id,
            )
        )

    async def clear_primary_for_athlete(
        self,
        athlete_id: uuid.UUID,
    ) -> None:
        await self.session.execute(
            update(AthleteCountryEligibility)
            .where(
                AthleteCountryEligibility.athlete_id == athlete_id,
                AthleteCountryEligibility.is_primary.is_(True),
            )
            .values(is_primary=False)
        )
        await self.session.flush()

    async def list_by_athlete(
        self,
        athlete_id: uuid.UUID,
    ) -> list[AthleteCountryEligibility]:
        result = await self.session.scalars(
            select(AthleteCountryEligibility)
            .where(
                AthleteCountryEligibility.athlete_id == athlete_id,
            )
            .order_by(
                AthleteCountryEligibility.is_primary.desc(),
                AthleteCountryEligibility.created_at.asc(),
            )
        )
        return list(result.all())
