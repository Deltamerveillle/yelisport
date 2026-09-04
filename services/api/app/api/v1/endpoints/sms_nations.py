"""SMS Nations athlete discovery endpoints."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
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
    league: Annotated[
        str | None,
        Query(min_length=1, max_length=180),
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
    min_age: Annotated[
        int | None,
        Query(ge=1, le=100),
    ] = None,
    max_age: Annotated[
        int | None,
        Query(ge=1, le=100),
    ] = None,
    talent_evaluated: bool | None = None,
    min_talent_score: Annotated[
        Decimal | None,
        Query(ge=0, le=100),
    ] = None,
    max_talent_score: Annotated[
        Decimal | None,
        Query(ge=0, le=100),
    ] = None,
    performance_metric: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=64,
            pattern=r"^[a-z][a-z0-9_]{0,63}$",
        ),
    ] = None,
    min_performance_value: Decimal | None = None,
    max_performance_value: Decimal | None = None,
    performance_verification_status: Literal[
        "declared",
        "documented",
        "verified",
    ]
    | None = None,
    performance_competition: Annotated[
        str | None,
        Query(min_length=1, max_length=180),
    ] = None,
    performance_since: date | None = None,
    performance_until: date | None = None,
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
    discipline, category, position, club, league, city, age,
    Talent evaluation, multisport performance and availability.

    Personal phone, email and WhatsApp information are never
    exposed by this endpoint.
    """

    del current_user

    if (
        min_age is not None
        and max_age is not None
        and min_age > max_age
    ):
        raise HTTPException(
            status_code=422,
            detail="min_age must be less than or equal to max_age",
        )

    if (
        min_talent_score is not None
        and max_talent_score is not None
        and min_talent_score > max_talent_score
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "min_talent_score must be less than or equal "
                "to max_talent_score"
            ),
        )

    if (
        (
            min_performance_value is not None
            or max_performance_value is not None
        )
        and performance_metric is None
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "performance_metric is required when filtering "
                "by performance value"
            ),
        )

    if (
        min_performance_value is not None
        and max_performance_value is not None
        and min_performance_value > max_performance_value
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "min_performance_value must be less than or equal "
                "to max_performance_value"
            ),
        )

    if (
        performance_since is not None
        and performance_until is not None
        and performance_since > performance_until
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "performance_since must be less than or equal "
                "to performance_until"
            ),
        )

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

    return SMSNationsSearchResponse(
        items=[
            SMSNationAthleteResponse.model_validate(item)
            for item in result.items
        ],
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )
