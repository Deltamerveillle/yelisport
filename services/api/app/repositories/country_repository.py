"""Repository for SMS Nations countries."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.country import Country


class CountryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        country_id: uuid.UUID,
    ) -> Country | None:
        return await self.session.get(Country, country_id)

    async def get_by_iso2(
        self,
        iso2: str,
    ) -> Country | None:
        return await self.session.scalar(
            select(Country).where(
                Country.iso2 == iso2.upper(),
                Country.is_active.is_(True),
            )
        )

    async def get_by_iso3(
        self,
        iso3: str,
    ) -> Country | None:
        return await self.session.scalar(
            select(Country).where(
                Country.iso3 == iso3.upper(),
                Country.is_active.is_(True),
            )
        )

    async def list_active(
        self,
        *,
        continent_code: str | None = None,
    ) -> list[Country]:
        query = select(Country).where(
            Country.is_active.is_(True),
        )

        if continent_code:
            query = query.where(
                Country.continent_code == continent_code.upper(),
            )

        query = query.order_by(Country.name.asc())

        result = await self.session.scalars(query)
        return list(result.all())
