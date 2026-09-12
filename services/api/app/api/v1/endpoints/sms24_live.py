"""Public SMS24 Live endpoints."""

from datetime import datetime
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.sms24_live_repository import SMS24LiveRepository
from app.schemas.sms24_live import (
    SMS24FixtureResponse,
    SMS24SourceHealthResponse,
    SMS24StandingResponse,
)
from app.services.sms24_live_service import SMS24LiveService

router = APIRouter(
    prefix="/sms24",
    tags=["sms24"],
)


def _service(
    session: AsyncSession,
) -> SMS24LiveService:
    return SMS24LiveService(
        SMS24LiveRepository(session)
    )


@router.get(
    "/live",
    response_model=list[SMS24FixtureResponse],
)
async def list_live(
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    sport: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=80,
            description="Sport slug",
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> list[SMS24FixtureResponse]:
    fixtures = await _service(session).list_live(
        sport_slug=sport,
        limit=limit,
        offset=offset,
    )

    return [
        SMS24FixtureResponse.model_validate(fixture)
        for fixture in fixtures
    ]


@router.get(
    "/fixtures",
    response_model=list[SMS24FixtureResponse],
)
async def list_fixtures(
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    sport: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=80,
            description="Sport slug",
        ),
    ] = None,
    status: Annotated[
        str | None,
        Query(
            pattern=(
                "^(scheduled|live|finished|postponed|"
                "cancelled|suspended|unknown)$"
            )
        ),
    ] = None,
    starts_from: datetime | None = None,
    starts_until: datetime | None = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> list[SMS24FixtureResponse]:
    fixtures = await _service(session).list_fixtures(
        status=status,
        sport_slug=sport,
        starts_from=starts_from,
        starts_until=starts_until,
        limit=limit,
        offset=offset,
    )

    return [
        SMS24FixtureResponse.model_validate(fixture)
        for fixture in fixtures
    ]


@router.get(
    "/fixtures/{fixture_id}",
    response_model=SMS24FixtureResponse,
)
async def get_fixture(
    fixture_id: uuid.UUID,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
) -> SMS24FixtureResponse:
    fixture = await _service(session).get_fixture(
        fixture_id
    )

    return SMS24FixtureResponse.model_validate(
        fixture
    )


@router.get(
    "/sources/health",
    response_model=list[SMS24SourceHealthResponse],
)
async def source_health(
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
) -> list[SMS24SourceHealthResponse]:
    sources = await _service(
        session
    ).list_source_health()

    return [
        SMS24SourceHealthResponse.model_validate(source)
        for source in sources
    ]


@router.get("/standings", response_model=list[SMS24StandingResponse])
async def list_standings(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    competition_id: uuid.UUID | None = None,
    season_id: uuid.UUID | None = None,
    sport: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SMS24StandingResponse]:
    standings = await _service(session).list_standings(
        competition_id=competition_id,
        season_id=season_id,
        sport_slug=sport,
        limit=limit,
        offset=offset,
    )
    return [SMS24StandingResponse.model_validate(row) for row in standings]
