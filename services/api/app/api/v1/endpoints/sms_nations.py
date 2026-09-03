"""SMS Nations athlete discovery endpoints."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db_session
from app.repositories.sms_nations_repository import SMSNationsRepository
from app.schemas.sms_nations import (
    SMSNationAthleteResponse,
    SMSNationsSearchResponse,
)
from app.services.sms_nations_service import SMSNationsService


router = APIRouter(
    prefix="/sms-nations",
    tags=["sms-nations"],
)


@router.get(
    "/athletes",
    response_model=SMSNationsSearchResponse,
)
async def search_sms_nations_athletes(
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    eligibility_country_id: uuid.UUID | None = None,
    sport_id: uuid.UUID | None = None,
    residence_country_id: uuid.UUID | None = None,
    discipline: Annotated[
        str | None,
        Query(min_length=1, max_length=100),
    ] = None,
    category: Annotated[
        str | None,
        Query(min_length=1, max_length=100),
    ] = None,
    position: Annotated[
        str | None,
        Query(min_length=1, max_length=100),
    ] = None,
    club: Annotated[
        str | None,
        Query(min_length=1, max_length=150),
    ] = None,
    city: Annotated[
        str | None,
        Query(min_length=1, max_length=120),
    ] = None,
    available_for_opportunities: bool | None = None,
    eligibility_status: Literal[
        "declared",
        "documented",
        "verified",
    ]
    | None = None,
    search: Annotated[
        str | None,
        Query(min_length=2, max_length=100),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 24,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> SMSNationsSearchResponse:
    """
    Search athletes through SMS Nations.

    Supports country eligibility, diaspora residence, sport,
    discipline, category, position, club, city and availability.

    Personal phone, email and WhatsApp information are never
    exposed by this endpoint.
    """

    del current_user

    result = await SMSNationsService(
        SMSNationsRepository(session)
    ).search_athletes(
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

    return SMSNationsSearchResponse(
        items=[
            SMSNationAthleteResponse.model_validate(item)
            for item in result.items
        ],
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )
