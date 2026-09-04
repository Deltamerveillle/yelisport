"""Service for SMS Nations athlete discovery."""

import uuid
from datetime import date
from decimal import Decimal

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
        league: str | None = None,
        city: str | None = None,
        available_for_opportunities: bool | None = None,
        eligibility_status: str | None = None,
        min_age: int | None = None,
        max_age: int | None = None,
        talent_evaluated: bool | None = None,
        min_talent_score: Decimal | None = None,
        max_talent_score: Decimal | None = None,
        performance_metric: str | None = None,
        min_performance_value: Decimal | None = None,
        max_performance_value: Decimal | None = None,
        performance_verification_status: str | None = None,
        performance_competition: str | None = None,
        performance_since: date | None = None,
        performance_until: date | None = None,
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
            league=league,
            city=city,
            available_for_opportunities=available_for_opportunities,
            eligibility_status=eligibility_status,
            min_age=min_age,
            max_age=max_age,
            talent_evaluated=talent_evaluated,
            min_talent_score=min_talent_score,
            max_talent_score=max_talent_score,
            performance_metric=performance_metric,
            min_performance_value=min_performance_value,
            max_performance_value=max_performance_value,
            performance_verification_status=(
                performance_verification_status
            ),
            performance_competition=performance_competition,
            performance_since=performance_since,
            performance_until=performance_until,
            search=search,
            limit=limit,
            offset=offset,
        )
