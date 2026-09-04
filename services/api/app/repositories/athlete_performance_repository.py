"""Repository for SMS athlete performances."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_performance import AthletePerformance


class AthletePerformanceRepository:
    """Database operations for multisport athlete performances."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        performance: AthletePerformance,
    ) -> AthletePerformance:
        self.session.add(performance)
        await self.session.flush()
        await self.session.refresh(performance)
        return performance

    async def get_by_id(
        self,
        performance_id: uuid.UUID,
    ) -> AthletePerformance | None:
        result = await self.session.execute(
            select(AthletePerformance).where(
                AthletePerformance.id == performance_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_athlete_id(
        self,
        athlete_id: uuid.UUID,
    ) -> Sequence[AthletePerformance]:
        result = await self.session.execute(
            select(AthletePerformance)
            .where(
                AthletePerformance.athlete_id == athlete_id
            )
            .order_by(
                AthletePerformance.performance_date.desc(),
                AthletePerformance.created_at.desc(),
            )
        )
        return result.scalars().all()

    async def update(
        self,
        performance: AthletePerformance,
    ) -> AthletePerformance:
        await self.session.flush()
        await self.session.refresh(performance)
        return performance

    async def delete(
        self,
        performance: AthletePerformance,
    ) -> None:
        await self.session.delete(performance)
        await self.session.flush()
