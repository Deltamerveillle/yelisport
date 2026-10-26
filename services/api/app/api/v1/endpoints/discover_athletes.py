"""SMS Discover athlete search API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.athlete_performance_repository import AthletePerformanceRepository
from app.repositories.discover_athlete_repository import DiscoverAthleteRepository
from app.repositories.discover_video_repository import DiscoverVideoRepository
from app.schemas.discover_athlete import (
    DiscoverAthleteProfileResponse,
    DiscoverAthleteResponse,
)
from app.services.discover_athlete_profile_service import (
    DiscoverAthleteProfileService,
)
from app.services.discover_athlete_service import DiscoverAthleteService
from app.sms24.player_statistics_evidence import AthleteStatisticsEvidenceReader

router = APIRouter(
    tags=["SMS Discover"],
)


@router.get(
    "/discover/athletes/{athlete_id}",
    response_model=DiscoverAthleteProfileResponse,
)
async def get_discover_athlete_profile(
    athlete_id: uuid.UUID,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
) -> DiscoverAthleteProfileResponse:
    """Return the public showcase of an opted-in SMS Discover athlete."""

    service = DiscoverAthleteProfileService(
        discover_repository=DiscoverAthleteRepository(session),
        performance_repository=AthletePerformanceRepository(session),
        statistics_reader=AthleteStatisticsEvidenceReader(session=session),
        video_repository=DiscoverVideoRepository(session),
    )
    return await service.get_profile(athlete_id)


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
    nationality_country_id: uuid.UUID | None = None,
    residence_country_id: uuid.UUID | None = None,
    discipline: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=120),
    position: str | None = Query(default=None, max_length=120),
    club_name: str | None = Query(default=None, max_length=180),
    league_name: str | None = Query(default=None, max_length=180),
    team_name: str | None = Query(default=None, max_length=180),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[DiscoverAthleteResponse]:
    """Search athletes who explicitly opted in to opportunities."""

    return await DiscoverAthleteService(session).search(
        sport_id=sport_id,
        nationality_country_id=nationality_country_id,
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
