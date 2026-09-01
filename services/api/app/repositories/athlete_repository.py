"""Persistence operations for athletes."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete


class AthleteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, athlete: Athlete) -> Athlete:
        """Create a new athlete."""
        self.session.add(athlete)
        await self.session.flush()
        return athlete

    async def get_by_id(self, athlete_id: uuid.UUID) -> Athlete | None:
        """Get an athlete by ID."""
        return await self.session.scalar(select(Athlete).where(Athlete.id == athlete_id))

    async def get_by_user_and_sport(
        self,
        user_id: uuid.UUID,
        sport_id: uuid.UUID,
    ) -> Athlete | None:
        """Get one athlete profile for a user and sport."""
        stmt = select(Athlete).where(
            Athlete.user_id == user_id,
            Athlete.sport_id == sport_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: uuid.UUID) -> list[Athlete]:
        """Get all athletes for a specific user."""
        result = await self.session.scalars(
            select(Athlete).where(Athlete.user_id == user_id).order_by(Athlete.created_at.desc())
        )
        return list(result.all())

    async def get_by_sport_id(self, sport_id: uuid.UUID) -> list[Athlete]:
        """Get all athletes for a specific sport."""
        result = await self.session.scalars(
            select(Athlete).where(Athlete.sport_id == sport_id).order_by(Athlete.created_at.desc())
        )
        return list(result.all())

    async def list_all(self) -> list[Athlete]:
        """List all athletes."""
        result = await self.session.scalars(select(Athlete).order_by(Athlete.created_at.desc()))
        return list(result.all())

    async def update(self, athlete: Athlete) -> Athlete:
        """Update an existing athlete."""
        await self.session.merge(athlete)
        await self.session.flush()
        return athlete

    async def delete(self, athlete_id: uuid.UUID) -> bool:
        """Delete an athlete by ID."""
        athlete = await self.get_by_id(athlete_id)
        if athlete:
            await self.session.delete(athlete)
            await self.session.flush()
            return True
        return False
