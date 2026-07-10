"""Persistence operations for the sport catalogue."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sport import Sport


class SportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> list[Sport]:
        result = await self.session.scalars(
            select(Sport).where(Sport.is_active.is_(True)).order_by(Sport.name)
        )
        return list(result.all())
