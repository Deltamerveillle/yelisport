"""SMS Passport persistence."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_passport import AthletePassport


class AthletePassportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, passport: AthletePassport) -> AthletePassport:
        self.session.add(passport)
        await self.session.flush()
        await self.session.refresh(passport)
        return passport

    async def get_by_id(
        self,
        passport_id: uuid.UUID,
    ) -> AthletePassport | None:
        stmt = select(AthletePassport).where(
            AthletePassport.id == passport_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_athlete_id(
        self,
        athlete_id: uuid.UUID,
    ) -> AthletePassport | None:
        stmt = select(AthletePassport).where(
            AthletePassport.athlete_id == athlete_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        passport: AthletePassport,
    ) -> AthletePassport:
        await self.session.flush()
        await self.session.refresh(passport)
        return passport

    async def delete(
        self,
        passport_id: uuid.UUID,
    ) -> bool:
        stmt = delete(AthletePassport).where(
            AthletePassport.id == passport_id
        )
        result = await self.session.execute(stmt)
        return bool(result.rowcount)
