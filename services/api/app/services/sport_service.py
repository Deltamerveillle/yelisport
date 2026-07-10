"""Sport catalogue use cases."""

from app.models.sport import Sport
from app.repositories.sport_repository import SportRepository


class SportService:
    def __init__(self, repository: SportRepository) -> None:
        self.repository = repository

    async def list_sports(self) -> list[Sport]:
        return await self.repository.list_active()
