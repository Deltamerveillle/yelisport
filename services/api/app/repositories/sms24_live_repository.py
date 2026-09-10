"""Read-side persistence for SMS24 Live."""

from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sport import Sport
from app.models.sports_live import (
    SportsCompetition,
    SportsCompetitor,
    SportsDataSource,
    SportsFixture,
    SportsFixtureParticipant,
)


@dataclass(slots=True)
class SMS24ParticipantView:
    competitor_id: uuid.UUID
    competitor_type: str
    name: str
    short_name: str | None
    country_code: str | None
    logo_url: str | None
    position: int
    role: str | None
    score: dict
    result_status: str | None


@dataclass(slots=True)
class SMS24FixtureView:
    id: uuid.UUID
    external_id: str
    sport_slug: str
    sport_name: str
    source_slug: str
    source_name: str
    competition_id: uuid.UUID | None
    competition_name: str | None
    competition_country_code: str | None
    season: str | None
    name: str | None
    starts_at: datetime
    status: str
    live_clock: str | None
    venue: str | None
    result: dict
    metadata: dict
    source_updated_at: datetime | None
    fetched_at: datetime
    participants: list[SMS24ParticipantView]


@dataclass(slots=True)
class SMS24SourceHealthView:
    id: uuid.UUID
    slug: str
    name: str
    provider_type: str
    priority: int
    health_status: str
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_checked_at: datetime | None


class SMS24LiveRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_fixtures(
        self,
        *,
        statuses: set[str] | None = None,
        sport_slug: str | None = None,
        starts_from: datetime | None = None,
        starts_until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SMS24FixtureView]:
        # Rank provider observations before pagination.
        #
        # Canonicalized observations sharing one canonical_fixture_id
        # form one public event. Legacy observations without a canonical
        # identity remain independent public rows.
        ranking_statement = (
            select(
                SportsFixture.id.label("fixture_id"),
                SportsFixture.starts_at.label("starts_at"),
                func.row_number()
                .over(
                    partition_by=(
                        SportsFixture.canonical_fixture_id.is_(None),
                        func.coalesce(
                            SportsFixture.canonical_fixture_id,
                            SportsFixture.id,
                        ),
                    ),
                    order_by=(
                        SportsDataSource.priority.asc(),
                        SportsFixture.fetched_at.desc(),
                        SportsFixture.id.asc(),
                    ),
                )
                .label("canonical_rank"),
            )
            .join(
                SportsDataSource,
                SportsDataSource.id == SportsFixture.source_id,
            )
            .join(
                Sport,
                Sport.id == SportsFixture.sport_id,
            )
            .where(
                SportsDataSource.is_active.is_(True),
                Sport.is_active.is_(True),
            )
        )

        if statuses:
            ranking_statement = ranking_statement.where(
                SportsFixture.status.in_(statuses)
            )

        if sport_slug:
            ranking_statement = ranking_statement.where(
                Sport.slug == sport_slug
            )

        if starts_from:
            ranking_statement = ranking_statement.where(
                SportsFixture.starts_at >= starts_from
            )

        if starts_until:
            ranking_statement = ranking_statement.where(
                SportsFixture.starts_at <= starts_until
            )

        ranked = ranking_statement.subquery()

        # Pagination applies to public canonical events, not raw
        # provider observations.
        selected_fixtures = (
            select(ranked.c.fixture_id)
            .where(ranked.c.canonical_rank == 1)
            .order_by(
                ranked.c.starts_at.asc(),
                ranked.c.fixture_id.asc(),
            )
            .limit(limit)
            .offset(offset)
            .subquery()
        )

        statement = (
            select(
                SportsFixture,
                SportsDataSource,
                SportsCompetition,
                Sport,
            )
            .join(
                selected_fixtures,
                selected_fixtures.c.fixture_id
                == SportsFixture.id,
            )
            .join(
                SportsDataSource,
                SportsDataSource.id == SportsFixture.source_id,
            )
            .join(
                Sport,
                Sport.id == SportsFixture.sport_id,
            )
            .outerjoin(
                SportsCompetition,
                SportsCompetition.id
                == SportsFixture.competition_id,
            )
            .order_by(
                SportsFixture.starts_at.asc(),
                SportsFixture.id.asc(),
            )
        )

        rows = (await self.session.execute(statement)).all()
        return await self._build_fixture_views(rows)

    async def get_fixture(
        self,
        fixture_id: uuid.UUID,
    ) -> SMS24FixtureView | None:
        statement = (
            select(
                SportsFixture,
                SportsDataSource,
                SportsCompetition,
                Sport,
            )
            .join(
                SportsDataSource,
                SportsDataSource.id == SportsFixture.source_id,
            )
            .join(
                Sport,
                Sport.id == SportsFixture.sport_id,
            )
            .outerjoin(
                SportsCompetition,
                SportsCompetition.id == SportsFixture.competition_id,
            )
            .where(
                SportsFixture.id == fixture_id,
                SportsDataSource.is_active.is_(True),
                Sport.is_active.is_(True),
            )
        )

        row = (await self.session.execute(statement)).first()
        if row is None:
            return None

        views = await self._build_fixture_views([row])
        return views[0]

    async def list_source_health(
        self,
    ) -> list[SMS24SourceHealthView]:
        result = await self.session.scalars(
            select(SportsDataSource)
            .where(SportsDataSource.is_active.is_(True))
            .order_by(
                SportsDataSource.priority.asc(),
                SportsDataSource.name.asc(),
            )
        )

        return [
            SMS24SourceHealthView(
                id=source.id,
                slug=source.slug,
                name=source.name,
                provider_type=source.provider_type,
                priority=source.priority,
                health_status=source.health_status,
                last_success_at=source.last_success_at,
                last_failure_at=source.last_failure_at,
                last_checked_at=source.last_checked_at,
            )
            for source in result.all()
        ]

    async def _build_fixture_views(
        self,
        rows: list,
    ) -> list[SMS24FixtureView]:
        if not rows:
            return []

        fixture_ids = [row[0].id for row in rows]

        participant_statement = (
            select(
                SportsFixtureParticipant,
                SportsCompetitor,
            )
            .join(
                SportsCompetitor,
                SportsCompetitor.id
                == SportsFixtureParticipant.competitor_id,
            )
            .where(
                SportsFixtureParticipant.fixture_id.in_(fixture_ids)
            )
            .order_by(
                SportsFixtureParticipant.fixture_id.asc(),
                SportsFixtureParticipant.position.asc(),
                SportsFixtureParticipant.id.asc(),
            )
        )

        participant_rows = (
            await self.session.execute(participant_statement)
        ).all()

        participants_by_fixture: dict[
            uuid.UUID,
            list[SMS24ParticipantView],
        ] = {}

        for participant, competitor in participant_rows:
            participants_by_fixture.setdefault(
                participant.fixture_id,
                [],
            ).append(
                SMS24ParticipantView(
                    competitor_id=competitor.id,
                    competitor_type=competitor.competitor_type,
                    name=competitor.name,
                    short_name=competitor.short_name,
                    country_code=competitor.country_code,
                    logo_url=competitor.logo_url,
                    position=participant.position,
                    role=participant.role,
                    score=participant.score_json or {},
                    result_status=participant.result_status,
                )
            )

        output: list[SMS24FixtureView] = []

        for fixture, source, competition, sport in rows:
            output.append(
                SMS24FixtureView(
                    id=fixture.id,
                    external_id=fixture.external_id,
                    sport_slug=sport.slug,
                    sport_name=sport.name,
                    source_slug=source.slug,
                    source_name=source.name,
                    competition_id=(
                        competition.id
                        if competition is not None
                        else None
                    ),
                    competition_name=(
                        competition.name
                        if competition is not None
                        else None
                    ),
                    competition_country_code=(
                        competition.country_code
                        if competition is not None
                        else None
                    ),
                    season=(
                        competition.season
                        if competition is not None
                        else None
                    ),
                    name=fixture.name,
                    starts_at=fixture.starts_at,
                    status=fixture.status,
                    live_clock=fixture.live_clock,
                    venue=fixture.venue,
                    result=fixture.result_json or {},
                    metadata=fixture.metadata_json or {},
                    source_updated_at=fixture.source_updated_at,
                    fetched_at=fixture.fetched_at,
                    participants=participants_by_fixture.get(
                        fixture.id,
                        [],
                    ),
                )
            )

        return output
