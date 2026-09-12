"""SMS24 Live public read use cases."""

from datetime import datetime
import uuid

from app.core.exceptions import NotFoundError
from app.repositories.sms24_live_repository import (
    SMS24FixtureView,
    SMS24LiveRepository,
    SMS24SourceHealthView,
    SMS24StandingView,
    SMS24CompetitionView,
    SMS24TeamView,
)


class SMS24LiveService:
    LIVE_STATUSES = {"live"}
    ALLOWED_STATUSES = {
        "scheduled",
        "live",
        "finished",
        "postponed",
        "cancelled",
        "suspended",
        "unknown",
    }

    def __init__(
        self,
        repository: SMS24LiveRepository,
    ) -> None:
        self.repository = repository

    async def list_live(
        self,
        *,
        sport_slug: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SMS24FixtureView]:
        return await self.repository.list_fixtures(
            statuses=self.LIVE_STATUSES,
            sport_slug=sport_slug,
            limit=limit,
            offset=offset,
        )

    async def list_fixtures(
        self,
        *,
        status: str | None = None,
        sport_slug: str | None = None,
        starts_from: datetime | None = None,
        starts_until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SMS24FixtureView]:
        statuses = {status} if status else None

        return await self.repository.list_fixtures(
            statuses=statuses,
            sport_slug=sport_slug,
            starts_from=starts_from,
            starts_until=starts_until,
            limit=limit,
            offset=offset,
        )

    async def get_fixture(
        self,
        fixture_id: uuid.UUID,
    ) -> SMS24FixtureView:
        fixture = await self.repository.get_fixture(fixture_id)

        if fixture is None:
            raise NotFoundError("Rencontre SMS24 introuvable")

        return fixture

    async def list_source_health(
        self,
    ) -> list[SMS24SourceHealthView]:
        return await self.repository.list_source_health()

    async def list_standings(
        self,
        *,
        competition_id: uuid.UUID | None = None,
        canonical_competitor_id: uuid.UUID | None = None,
        season_id: uuid.UUID | None = None,
        sport_slug: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SMS24StandingView]:
        return await self.repository.list_standings(
            competition_id=competition_id,
            canonical_competitor_id=canonical_competitor_id,
            season_id=season_id,
            sport_slug=sport_slug,
            limit=limit,
            offset=offset,
        )

    async def get_competition(
        self, competition_id: uuid.UUID, *, season_id: uuid.UUID | None = None,
    ) -> SMS24CompetitionView:
        competition = await self.repository.get_competition(competition_id)
        if competition is None:
            raise NotFoundError("Compétition SMS24 introuvable")
        if season_id is not None:
            if not any(season.id == season_id for season in competition.seasons):
                raise NotFoundError("Saison SMS24 introuvable pour cette compétition")
            competition.selected_season_id = season_id
        else:
            current = [season.id for season in competition.seasons if season.is_current]
            competition.selected_season_id = current[0] if len(current) == 1 else None
        return competition

    async def get_team(self, canonical_competitor_id: uuid.UUID) -> SMS24TeamView:
        team = await self.repository.get_team(canonical_competitor_id)
        if team is None:
            raise NotFoundError("Équipe SMS24 introuvable")
        return team

    async def list_competition_fixtures(
        self, competition_id: uuid.UUID, *, status: str | None = None,
        starts_from: datetime | None = None, starts_until: datetime | None = None,
        limit: int = 50, offset: int = 0,
    ) -> list[SMS24FixtureView]:
        await self.get_competition(competition_id)
        return await self.repository.list_fixtures(
            canonical_competition_id=competition_id, statuses={status} if status else None,
            starts_from=starts_from, starts_until=starts_until, limit=limit, offset=offset,
        )

    async def list_team_fixtures(
        self, canonical_competitor_id: uuid.UUID, *, status: str | None = None,
        starts_from: datetime | None = None, starts_until: datetime | None = None,
        limit: int = 50, offset: int = 0,
    ) -> list[SMS24FixtureView]:
        await self.get_team(canonical_competitor_id)
        return await self.repository.list_fixtures(
            canonical_competitor_id=canonical_competitor_id, statuses={status} if status else None,
            starts_from=starts_from, starts_until=starts_until, limit=limit, offset=offset,
        )
