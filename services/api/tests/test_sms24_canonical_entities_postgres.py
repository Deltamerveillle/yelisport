"""PostgreSQL coverage of canonical entity wiring through real ingestion."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sport import Sport
from app.models.sports_live import (
    SportsCanonicalCompetition,
    SportsCanonicalCompetitor,
    SportsCanonicalFixture,
    SportsCompetition,
    SportsCompetitor,
    SportsDataSource,
    SportsFixture,
    SportsSeason,
)
from app.repositories.sms24_live_repository import SMS24LiveRepository
from app.sms24.ingestion import SMS24IngestionRepository, SMS24IngestionService
from app.sms24.providers import (
    ProviderCompetition,
    ProviderFetchResult,
    ProviderFixture,
    ProviderParticipant,
)
from tests.test_sms24_ingestion_postgres import _test_engine


@pytest.mark.asyncio
async def test_canonical_entities_ingestion_seasons_and_fixture_compatibility():
    # The service commits; bind it to an outer transaction so all test data rolls back.
    async with _test_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with AsyncSession(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as session:
                sport = Sport(slug=f"sms24-entities-{uuid.uuid4().hex[:12]}", name="Test sport")
                sources = [
                    SportsDataSource(
                        slug=f"sms24-entities-{uuid.uuid4().hex[:12]}",
                        name=f"Provider {i}",
                        priority=i,
                    )
                    for i in range(2)
                ]
                session.add_all([sport, *sources])
                await session.flush()
                repository = SMS24IngestionRepository(session)
                service = SMS24IngestionService(repository)
                now = datetime(2026, 9, 10, 18, tzinfo=UTC)
                for i, source in enumerate(sources):
                    await service.ingest_provider_result(
                        provider=SimpleNamespace(slug=source.slug),
                        result=ProviderFetchResult(
                            fetched_at=now,
                            fixtures=[
                                ProviderFixture(
                                    external_id=f"fixture-{i}",
                                    sport_slug=sport.slug,
                                    starts_at=now,
                                    status="scheduled",
                                    competition=ProviderCompetition(
                                        jurisdiction_name="England",
                                        external_id=f"league-{i}",
                                        name=["Premier League", "PREMIER  LEAGUE"][i],
                                        country_code="GB",
                                        season=["Season 2026", "SEASON  2026"][i],
                                    ),
                                    participants=[
                                        ProviderParticipant(
                                            external_id=f"team-{i}",
                                            name=["St. Mirren", "ST Mirren"][i],
                                            country_code="GB",
                                        ),
                                        ProviderParticipant(
                                            external_id=f"opponent-{i}", name="Opponent"
                                        ),
                                    ],
                                )
                            ],
                        ),
                    )
                competitions = list(
                    (
                        await session.scalars(
                            select(SportsCompetition).where(
                                SportsCompetition.sport_id == sport.id,
                            )
                        )
                    ).all()
                )
                assert len(competitions) == 2
                canonical_id = competitions[0].canonical_competition_id
                assert canonical_id is not None
                assert {c.canonical_competition_id for c in competitions} == {canonical_id}
                assert {c.name for c in competitions} == {"Premier League", "PREMIER  LEAGUE"}
                teams = list(
                    (
                        await session.scalars(
                            select(SportsCompetitor).where(
                                SportsCompetitor.sport_id == sport.id,
                                SportsCompetitor.country_code == "GB",
                            )
                        )
                    ).all()
                )
                assert len(teams) == 2
                assert teams[0].canonical_competitor_id == teams[1].canonical_competitor_id
                assert teams[0].canonical_competitor_id is not None
                seasons = list(
                    (
                        await session.scalars(
                            select(SportsSeason).where(
                                SportsSeason.canonical_competition_id == canonical_id,
                            )
                        )
                    ).all()
                )
                assert len(seasons) == 1
                assert seasons[0].is_current is False
                assert seasons[0].starts_at is None and seasons[0].ends_at is None
                assert (
                    await repository.resolve_season(
                        canonical_competition_id=canonical_id,
                        label="season 2026",
                    )
                ).id == seasons[0].id
                for label in ["2026", "2026/27", "2026-2027", "Tour A"]:
                    await repository.resolve_season(
                        canonical_competition_id=canonical_id, label=label
                    )
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(SportsSeason)
                        .where(
                            SportsSeason.canonical_competition_id == canonical_id,
                        )
                    )
                    == 5
                )

                other = await repository.upsert_competition(
                    sport_id=sport.id,
                    source_id=sources[0].id,
                    fetched_at=now,
                    competition=ProviderCompetition(
                        jurisdiction_name="England",
                        external_id="other",
                        name="Premier Division",
                        country_code="GB",
                        season="Season 2026",
                    ),
                )
                assert other.canonical_competition_id != canonical_id
                different_team = await repository.upsert_competitor(
                    sport_id=sport.id,
                    source_id=sources[0].id,
                    fetched_at=now,
                    participant=ProviderParticipant(
                        external_id="different",
                        name="Saint Mirren",
                        country_code="GB",
                    ),
                )
                assert different_team.canonical_competitor_id != teams[0].canonical_competitor_id

                # Existing provider IDs survive updates while canonical links follow exact identity.
                old_id = other.id
                updated = await repository.upsert_competition(
                    sport_id=sport.id,
                    source_id=sources[0].id,
                    fetched_at=now,
                    competition=ProviderCompetition(
                        jurisdiction_name="England",
                        external_id="other",
                        name="Premier League",
                        country_code="GB",
                        season="2027",
                    ),
                )
                assert updated.id == old_id and updated.canonical_competition_id == canonical_id
                updated_team = await repository.upsert_competitor(
                    sport_id=sport.id,
                    source_id=sources[0].id,
                    fetched_at=now,
                    participant=ProviderParticipant(
                        external_id="different",
                        name="St Mirren",
                        country_code="GB",
                    ),
                )
                assert updated_team.id == different_team.id
                assert updated_team.canonical_competitor_id == teams[0].canonical_competitor_id

                fixtures = list(
                    (
                        await session.scalars(
                            select(SportsFixture).where(
                                SportsFixture.sport_id == sport.id,
                            )
                        )
                    ).all()
                )
                assert len(fixtures) == 2
                assert fixtures[0].canonical_fixture_id == fixtures[1].canonical_fixture_id
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(SportsCanonicalFixture)
                        .where(
                            SportsCanonicalFixture.sport_id == sport.id,
                        )
                    )
                    == 1
                )
                public = await SMS24LiveRepository(session).list_fixtures(sport_slug=sport.slug)
                assert len(public) == 1
                assert public[0].source_slug == sources[0].slug
                assert public[0].season == "Season 2026"

                # FK actions preserve observations and cascade only canonical-owned seasons.
                await session.execute(
                    delete(SportsCanonicalCompetition).where(
                        SportsCanonicalCompetition.id == canonical_id,
                    )
                )
                await session.execute(
                    delete(SportsCanonicalCompetitor).where(
                        SportsCanonicalCompetitor.id == teams[0].canonical_competitor_id,
                    )
                )
                await session.refresh(competitions[0])
                await session.refresh(teams[0])
                assert competitions[0].canonical_competition_id is None
                assert teams[0].canonical_competitor_id is None
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(SportsSeason)
                        .where(
                            SportsSeason.canonical_competition_id == canonical_id,
                        )
                    )
                    == 0
                )
        finally:
            await transaction.rollback()
