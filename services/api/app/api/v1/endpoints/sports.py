"""Authenticated sport catalogue endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db_session
from app.repositories.sport_repository import SportRepository
from app.schemas.sport import SportResponse
from app.services.sport_service import SportService

router = APIRouter(prefix="/sports", tags=["sports"])


@router.get("", response_model=list[SportResponse])
async def list_sports(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    search: Annotated[str | None, Query(min_length=2, max_length=80)] = None,
) -> list[SportResponse]:
    del current_user
    sports = await SportService(SportRepository(session)).list_sports(search)
    return [SportResponse.model_validate(sport) for sport in sports]


@router.get("/{slug}", response_model=SportResponse)
async def get_sport(
    slug: str,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SportResponse:
    del current_user
    sport = await SportService(SportRepository(session)).get_sport(slug)
    return SportResponse.model_validate(sport)
