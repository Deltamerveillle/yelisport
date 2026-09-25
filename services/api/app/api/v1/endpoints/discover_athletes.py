"""SMS Discover athlete search API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.discover_athlete import DiscoverAthleteResponse
from app.services.discover_athlete_service import DiscoverAthleteService

router = APIRouter(
    tags=["SMS Discover"],
)


@router.get(
    "/discover/athletes",
    response_model=list[DiscoverAthleteResponse],
)
async def search_discover_athletes(
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    sport_id: uuid.UUID | None = None,
    residence_country_id: uuid.UUID | None = None,
    discipline: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=120),
    position: str | None = Query(default=None, max_length=120),
    club_name: str | None = Query(default=None, max_length=180),
    league_name: str | None = Query(default=None, max_length=180),
    team_name: str | None = Query(default=None, max_length=180),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Search athletes who explicitly opted in to opportunities."""

    return await DiscoverAthleteService(session).search(
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
