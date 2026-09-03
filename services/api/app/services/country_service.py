"""Country catalogue service."""

from app.core.exceptions import NotFoundError
from app.repositories.country_repository import CountryRepository


class CountryService:
    def __init__(self, country_repository: CountryRepository) -> None:
        self.country_repository = country_repository

    async def list_countries(
        self,
        *,
        continent_code: str | None = None,
        search: str | None = None,
    ):
        countries = await self.country_repository.list_active(
            continent_code=continent_code,
        )

        if search:
            needle = search.strip().lower()
            countries = [
                country
                for country in countries
                if needle in country.name.lower()
                or needle in country.iso2.lower()
                or needle in country.iso3.lower()
            ]

        return countries

    async def get_country(self, iso2: str):
        country = await self.country_repository.get_by_iso2(
            iso2.strip().upper()
        )

        if country is None:
            raise NotFoundError("Country not found")

        return country
