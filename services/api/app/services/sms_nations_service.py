"""Service for SMS Nations athlete discovery."""

import uuid

from app.repositories.sms_nations_repository import (
    SMSNationsRepository,
    SMSNationsSearchResult,
)


class SMSNationsService:
    """Application service for SMS Nations search."""

    def __init__(
        self,
        repository: SMSNationsRepository,
    ) -> None:
        self.repository = repository

    async def search_athletes(
        self,
        *,
        eligibility_country_id: uuid.UUID | None = None,
        sport_id: uuid.UUID | None = None,
        residence_country_id: uuid.UUID | None = None,
        discipline: str | None = None,
        category: str | None = None,
        position: str | None = None,
        club: str | None = None,
        city: str | None = None,
        available_for_opportunities: bool | None = None,
        eligibility_status: str | None = None,
        search: str | None = None,
        limit: int = 24,
        offset: int = 0,
    ) -> SMSNationsSearchResult:
        return await self.repository.search_athletes(
            eligibility_country_id=eligibility_country_id,
            sport_id=sport_id,
            residence_country_id=residence_country_id,
            discipline=discipline,
            category=category,
            position=position,
            club=club,
            city=city,
            available_for_opportunities=available_for_opportunities,
            eligibility_status=eligibility_status,
            search=search,
            limit=limit,
            offset=offset,
        )
