"""Local statistics observations and explicit graph resolution, never SMS Proof.

The caller owns the transaction. Savepoints isolate invalid attempts; SQL errors
propagate. Only this observation table is written, never any human/graph entity.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sports_live import (
    SportsCanonicalCompetition,
    SportsCanonicalCompetitor,
    SportsCanonicalFixture,
    SportsCompetition,
    SportsCompetitor,
    SportsFixture,
    SportsSeason,
)
from app.models.sports_player_statistics import SportsPlayerStatisticObservation
from app.sms24.providers.player_statistics import (
    ProviderPlayerStatistic,
    build_player_statistic_observation_key,
    validate_statistics_timestamp,
)


class SMS24PlayerStatisticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _locked(self, model, identity):
        row = await self.session.scalar(
            select(model)
            .where(model.id == identity)
            .with_for_update()
            .execution_options(populate_existing=True),
        )
        if row is None:
            raise ValueError("Unknown explicit statistics graph identity")
        return row

    async def _validate_graph(
        self,
        row,
        *,
        athlete_competitor_id,
        fixture_id,
        canonical_fixture_id,
        season_id,
        fixture_external_id,
    ) -> None:
        if athlete_competitor_id is not None:
            athlete = await self._locked(SportsCompetitor, athlete_competitor_id)
            if (
                athlete.sport_id != row.sport_id
                or athlete.source_id != row.source_id
                or athlete.competitor_type != "athlete"
                or athlete.external_id != row.athlete_external_id
            ):
                raise ValueError("Statistics athlete must match source, ID, sport and type")
            if athlete.canonical_competitor_id is not None:
                canonical = await self._locked(
                    SportsCanonicalCompetitor,
                    athlete.canonical_competitor_id,
                )
                if canonical.sport_id != row.sport_id or canonical.competitor_type != "athlete":
                    raise ValueError("Incompatible canonical athlete graph")
        fixture = None
        competition = None
        if fixture_id is not None:
            fixture = await self._locked(SportsFixture, fixture_id)
            if (
                fixture.sport_id != row.sport_id
                or fixture.source_id != row.source_id
                or (fixture_external_id is not None and fixture.external_id != fixture_external_id)
            ):
                raise ValueError("Statistics fixture must match source, ID and sport")
            if fixture.competition_id is not None:
                competition = await self._locked(SportsCompetition, fixture.competition_id)
                if competition.sport_id != row.sport_id or competition.source_id != row.source_id:
                    raise ValueError("Incompatible provider competition graph")
                if competition.canonical_competition_id is not None:
                    canonical = await self._locked(
                        SportsCanonicalCompetition,
                        competition.canonical_competition_id,
                    )
                    if canonical.sport_id != row.sport_id:
                        raise ValueError("Incompatible canonical competition sport")
            if fixture.canonical_fixture_id is not None:
                canonical = await self._locked(SportsCanonicalFixture, fixture.canonical_fixture_id)
                if canonical.sport_id != row.sport_id:
                    raise ValueError("Incompatible canonical fixture sport")
        if canonical_fixture_id is not None:
            if fixture is None or fixture.canonical_fixture_id != canonical_fixture_id:
                raise ValueError("Canonical fixture requires the explicit provider fixture mapping")
        if season_id is not None:
            season = await self._locked(SportsSeason, season_id)
            canonical = await self._locked(
                SportsCanonicalCompetition,
                season.canonical_competition_id,
            )
            if canonical.sport_id != row.sport_id:
                raise ValueError("Incompatible statistics season sport")
            if fixture is not None and (
                competition is None
                or competition.canonical_competition_id != season.canonical_competition_id
            ):
                raise ValueError("Season requires a matching explicit fixture competition mapping")

    async def record_observation(
        self,
        *,
        source_id: uuid.UUID,
        sport_id: uuid.UUID,
        statistic: ProviderPlayerStatistic,
        fetched_at: datetime,
    ) -> SportsPlayerStatisticObservation:
        validate_statistics_timestamp(fetched_at, required=True)
        key = build_player_statistic_observation_key(statistic)
        values = {
            name: getattr(statistic, name)
            for name in (
                "external_id",
                "record_reference",
                "athlete_external_id",
                "athlete_name",
                "fixture_external_id",
                "scope",
                "period_label",
                "source_updated_at",
            )
        }
        values.update(
            metrics_json=statistic.metrics, metadata_json=statistic.metadata, fetched_at=fetched_at
        )
        async with self.session.begin_nested():
            # The unique constraint arbitrates concurrent first inserts. Lock the
            # winner before validating any existing graph or updating its snapshot.
            await self.session.execute(
                insert(SportsPlayerStatisticObservation)
                .values(
                    source_id=source_id,
                    sport_id=sport_id,
                    observation_key=key,
                    **values,
                )
                .on_conflict_do_nothing(constraint="uq_sports_player_stats_observation"),
            )
            row = await self.session.scalar(
                select(SportsPlayerStatisticObservation)
                .where(
                    SportsPlayerStatisticObservation.source_id == source_id,
                    SportsPlayerStatisticObservation.observation_key == key,
                )
                .with_for_update()
                .execution_options(populate_existing=True),
            )
            if row.sport_id != sport_id or row.athlete_external_id != statistic.athlete_external_id:
                raise ValueError("A statistics record cannot change sport or athlete implicitly")
            if fetched_at < row.fetched_at:
                return row
            await self._validate_graph(
                row,
                athlete_competitor_id=row.athlete_competitor_id,
                fixture_id=row.fixture_id,
                canonical_fixture_id=row.canonical_fixture_id,
                season_id=row.season_id,
                fixture_external_id=statistic.fixture_external_id,
            )
            for name, value in values.items():
                setattr(row, name, value)
            row.updated_at = func.now()
            await self.session.flush()
            await self.session.refresh(row)
            return row

    async def resolve_observation(
        self,
        *,
        observation_id: uuid.UUID,
        athlete_competitor_id: uuid.UUID,
        fixture_id: uuid.UUID | None = None,
        canonical_fixture_id: uuid.UUID | None = None,
        season_id: uuid.UUID | None = None,
    ) -> SportsPlayerStatisticObservation:
        """Add exact authorized mappings; omitted optional IDs retain existing ones.

        Replacements/removals require a future explicit reconciliation workflow.
        No season label, canonical key or athlete name is parsed or compared.
        """
        async with self.session.begin_nested():
            row = await self._locked(SportsPlayerStatisticObservation, observation_id)
            proposed = dict(
                athlete_competitor_id=athlete_competitor_id,
                fixture_id=fixture_id,
                canonical_fixture_id=canonical_fixture_id,
                season_id=season_id,
            )
            for name, identity in proposed.items():
                current = getattr(row, name)
                if current is not None and identity is not None and current != identity:
                    raise ValueError("Existing statistics mapping requires explicit reconciliation")
                proposed[name] = current if identity is None else identity
            if athlete_competitor_id is None:
                raise ValueError("An explicit provider athlete identity is required")
            if row.fixture_id is None and proposed["fixture_id"] is not None:
                if row.fixture_external_id is None:
                    raise ValueError("Fixture resolution requires a reported provider fixture ID")
            await self._validate_graph(row, **proposed, fixture_external_id=row.fixture_external_id)
            for name, identity in proposed.items():
                setattr(row, name, identity)
            await self.session.flush()
            return row
