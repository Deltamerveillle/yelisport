"""Sport catalogue use cases."""

from app.core.exceptions import NotFoundError
from app.models.sport import Sport
from app.repositories.sport_repository import SportRepository


class SportService:
    def __init__(self, repository: SportRepository) -> None:
        self.repository = repository

    async def list_sports(self, search: str | None = None) -> list[Sport]:
        return await self.repository.list_active(search)

    async def get_sport(self, slug: str) -> Sport:
        sport = await self.repository.get_active_by_slug(slug)
        if sport is None:
            raise NotFoundError("Sport introuvable")
        return sport
