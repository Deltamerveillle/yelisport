"""Read-only athlete discovery for SMS Discover."""

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.athlete_passport import AthletePassport


@dataclass(frozen=True, slots=True)
class DiscoverAthleteResult:
    athlete: Athlete
    passport: AthletePassport


class DiscoverAthleteRepository:
    """Search athletes who explicitly opted in to opportunities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
    ) -> list[DiscoverAthleteResult]:
        stmt: Select[tuple[Athlete, AthletePassport]] = (
            select(Athlete, AthletePassport)
            .join(
                AthletePassport,
                AthletePassport.athlete_id == Athlete.id,
            )
            .where(AthletePassport.available_for_opportunities.is_(True))
        )

        if sport_id is not None:
            stmt = stmt.where(Athlete.sport_id == sport_id)

        if residence_country_id is not None:
            stmt = stmt.where(
                Athlete.residence_country_id == residence_country_id
            )

        filters = (
            (AthletePassport.discipline, discipline),
            (AthletePassport.category, category),
            (AthletePassport.position, position),
            (AthletePassport.club_name, club_name),
            (AthletePassport.league_name, league_name),
            (AthletePassport.team_name, team_name),
        )

        for column, value in filters:
            if value is not None:
                normalized = value.strip()
                if normalized:
                    stmt = stmt.where(column.ilike(normalized))

        stmt = (
            stmt.order_by(
                Athlete.updated_at.desc(),
                Athlete.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)

        return [
            DiscoverAthleteResult(
                athlete=athlete,
                passport=passport,
            )
            for athlete, passport in result.all()
        ]

    async def get_discoverable_by_athlete_id(
        self,
        athlete_id: uuid.UUID,
    ) -> DiscoverAthleteResult | None:
        stmt: Select[tuple[Athlete, AthletePassport]] = (
            select(Athlete, AthletePassport)
            .join(
                AthletePassport,
                AthletePassport.athlete_id == Athlete.id,
            )
            .where(
                Athlete.id == athlete_id,
                AthletePassport.available_for_opportunities.is_(True),
            )
        )

        result = await self.session.execute(stmt)
        row = result.one_or_none()

        if row is None:
            return None

        athlete, passport = row
        return DiscoverAthleteResult(
            athlete=athlete,
            passport=passport,
        )
