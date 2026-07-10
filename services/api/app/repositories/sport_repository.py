"""Persistence operations for the sport catalogue."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sport import Sport


class SportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self, search: str | None = None) -> list[Sport]:
        statement = select(Sport).where(Sport.is_active.is_(True))
        if search:
            statement = statement.where(Sport.name.icontains(search, autoescape=True))
        result = await self.session.scalars(statement.order_by(Sport.name))
        return list(result.all())

    async def get_active_by_slug(self, slug: str) -> Sport | None:
        return await self.session.scalar(
            select(Sport).where(Sport.slug == slug, Sport.is_active.is_(True))
        )
