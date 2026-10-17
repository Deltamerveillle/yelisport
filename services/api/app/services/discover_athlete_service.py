"""Application service for SMS Discover athlete search."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.discover_athlete_repository import DiscoverAthleteRepository
from app.schemas.athlete_passport import AthletePassportResponse
from app.schemas.discover_athlete import (
    DiscoverAthleteIdentityResponse,
    DiscoverAthleteResponse,
)


class DiscoverAthleteService:
    """Expose athletes who explicitly opted in to opportunity discovery."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = DiscoverAthleteRepository(session)

    async def search(
        self,
        *,
        sport_id: uuid.UUID | None = None,
        residence_country_id: uuid.UUID | None = None,
        discipline: str | None = None,
        category: str | None = None,
        position: str | None = None,
        club_name: str | None = None,
        league_name: str | None = None,
        team_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DiscoverAthleteResponse]:
        results = await self.repository.search(
            sport_id=sport_id,
            residence_country_id=residence_country_id,
            discipline=discipline,
            category=category,
            position=position,
            club_name=club_name,
            league_name=league_name,
            team_name=team_name,
            limit=limit,
            offset=offset,
        )

        return [
            DiscoverAthleteResponse(
                athlete=DiscoverAthleteIdentityResponse.model_validate(result.athlete),
                passport=AthletePassportResponse.model_validate(result.passport),
            )
            for result in results
        ]
