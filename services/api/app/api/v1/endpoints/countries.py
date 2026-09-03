"""Authenticated country catalogue endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db_session
from app.repositories.country_repository import CountryRepository
from app.schemas.country import CountryResponse
from app.services.country_service import CountryService

router = APIRouter(prefix="/countries", tags=["countries"])


@router.get("", response_model=list[CountryResponse])
async def list_countries(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    continent_code: Annotated[
        str | None,
        Query(min_length=2, max_length=2),
    ] = None,
    search: Annotated[
        str | None,
        Query(min_length=2, max_length=80),
    ] = None,
) -> list[CountryResponse]:
    del current_user

    countries = await CountryService(
        CountryRepository(session)
    ).list_countries(
        continent_code=(
            continent_code.upper()
            if continent_code
            else None
        ),
        search=search,
    )

    return [
        CountryResponse.model_validate(country)
        for country in countries
    ]


@router.get("/{iso2}", response_model=CountryResponse)
async def get_country(
    iso2: str,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CountryResponse:
    del current_user

    country = await CountryService(
        CountryRepository(session)
    ).get_country(iso2)

    return CountryResponse.model_validate(country)
