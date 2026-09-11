"""PostgreSQL regression coverage for 0029 conservative entity identities."""

import importlib
from datetime import UTC, datetime

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select

from app.models.sports_live import (
    SportsCanonicalCompetition,
    SportsCanonicalCompetitor,
    SportsCompetition,
    SportsCompetitor,
    SportsSeason,
)
from app.sms24.backfill_entities import backfill_historical_canonical_entities
from app.sms24.ingestion import SMS24IngestionRepository
from app.sms24.providers import ProviderCompetition, ProviderParticipant
from tests.test_sms24_backfill_entities_postgres import (
    competition,
    competitor,
    count,
    seed,
)
from tests.test_sms24_backfill_entities_postgres import (
    session as isolated_session,
)

session = isolated_session

NOW = datetime(2026, 9, 11, tzinfo=UTC)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "first", "second"),
    [
        ("Premier League", "Uganda", "Bhutan"),
        ("Premier League", "England", "Uganda"),
        ("Cup", "Greece", "Russia"),
        ("Premier League", "England", "Scotland"),
    ],
)
async def test_jurisdictions_prevent_false_competition_merges(session, name, first, second):
    sport, sources = await seed(session)
    repo = SMS24IngestionRepository(session)
    rows = []
    for source, jurisdiction in zip(sources, [first, second], strict=True):
        rows.append(
            await repo.upsert_competition(
                source_id=source.id,
                sport_id=sport.id,
                fetched_at=NOW,
                competition=ProviderCompetition(
                    external_id="1",
                    name=name,
                    jurisdiction_name=jurisdiction,
                    country_code="GB",
                ),
            )
        )
    assert rows[0].canonical_competition_id != rows[1].canonical_competition_id
    assert rows[0].normalized_jurisdiction == first.casefold()
    assert await count(session, SportsCanonicalCompetition) == 2


@pytest.mark.asyncio
async def test_unknown_competitions_are_observation_scoped_and_enrichment_is_explicit(session):
    sport, sources = await seed(session)
    repo = SMS24IngestionRepository(session)

    async def upsert(source, external, jurisdiction=None, name="Premier League"):
        return await repo.upsert_competition(
            source_id=source.id,
            sport_id=sport.id,
            fetched_at=NOW,
            competition=ProviderCompetition(
                external_id=external,
                name=name,
                jurisdiction_name=jurisdiction,
                country_code="GB",
            ),
        )

    a = await upsert(sources[0], "1")
    original = a.canonical_competition_id
    b = await upsert(sources[0], "2")
    c = await upsert(sources[1], "1")
    assert (
        len({a.canonical_competition_id, b.canonical_competition_id, c.canonical_competition_id})
        == 3
    )
    again = await upsert(sources[0], "1", name="Renamed league")
    assert again.id == a.id and again.canonical_competition_id == original
    assert (
        await session.get(SportsCanonicalCompetition, original)
    ).identity_scope == "provider_scoped"
    enriched = await upsert(sources[0], "1", "Uganda")
    assert enriched.canonical_competition_id != original
    assert b.canonical_competition_id != enriched.canonical_competition_id
    matching = await upsert(sources[1], "verified", " UGANDA ", "PREMIER  LEAGUE")
    assert matching.canonical_competition_id == enriched.canonical_competition_id
    canonical = await session.get(SportsCanonicalCompetition, enriched.canonical_competition_id)
    assert canonical.identity_scope == "verified_context"
    assert canonical.normalized_jurisdiction == "uganda"


@pytest.mark.asyncio
async def test_unknown_arsenal_and_cross_provider_rangers_never_merge_by_name(session):
    sport, sources = await seed(session)
    repo = SMS24IngestionRepository(session)
    ids = []
    for source, external, name in [
        (sources[0], "42", "Arsenal"),
        (sources[0], "9419", "Arsenal"),
        (sources[0], "r", "Rangers"),
        (sources[1], "r", "RANGERS"),
    ]:
        observation = await repo.upsert_competitor(
            sport_id=sport.id,
            source_id=source.id,
            fetched_at=NOW,
            participant=ProviderParticipant(external_id=external, name=name),
        )
        ids.append(observation.canonical_competitor_id)
    assert len(set(ids)) == 4
    again = await repo.upsert_competitor(
        sport_id=sport.id,
        source_id=sources[0].id,
        fetched_at=NOW,
        participant=ProviderParticipant(external_id="42", name="ARSENAL FC"),
    )
    assert again.canonical_competitor_id == ids[0]
    assert await count(session, SportsCompetitor) == 4
    assert await count(session, SportsCanonicalCompetitor) == 4
    assert all(
        row.identity_scope == "provider_scoped"
        for row in (await session.scalars(select(SportsCanonicalCompetitor)))
    )


@pytest.mark.asyncio
async def test_historical_missing_context_stays_separate_and_known_context_converges(session):
    sport, sources = await seed(session)
    unknown = [
        competition(sport, source, "Cup", jurisdiction_name=None, country_code=None)
        for source in sources
    ]
    known = [
        competition(sport, source, name, "2026/27", jurisdiction_name=jurisdiction)
        for source, name, jurisdiction in [
            (sources[0], "Premier League", "Uganda"),
            (sources[1], "PREMIER  LEAGUE", "UGANDA"),
        ]
    ]
    teams = [competitor(sport, sources[0], "Arsenal", country_code=None) for _ in range(2)]
    teams[0].external_id, teams[1].external_id = "42", "9419"
    session.add_all([*unknown, *known, *teams])
    first = await backfill_historical_canonical_entities(session)
    assert first.competitions_resolved == 4 and first.competitors_resolved == 2
    assert unknown[0].canonical_competition_id != unknown[1].canonical_competition_id
    assert known[0].canonical_competition_id == known[1].canonical_competition_id
    assert teams[0].canonical_competitor_id != teams[1].canonical_competitor_id
    assert first.seasons_total == 1
    second = await backfill_historical_canonical_entities(session)
    assert (
        second.competitions_processed
        == second.competitors_processed
        == second.seasons_processed
        == 0
    )
    assert second.canonical_competitions_total == 3
    assert second.canonical_competitors_total == 2


@pytest.mark.asyncio
async def test_migration_round_trip_preserves_legacy_rows_without_endorsing_unsafe_links(session):
    sport, sources = await seed(session)
    repo = SMS24IngestionRepository(session)
    observation = await repo.upsert_competition(
        sport_id=sport.id,
        source_id=sources[0].id,
        fetched_at=NOW,
        competition=ProviderCompetition(external_id="old", name="Cup", season="2026"),
    )
    team = await repo.upsert_competitor(
        sport_id=sport.id,
        source_id=sources[0].id,
        fetched_at=NOW,
        participant=ProviderParticipant(external_id="42", name="Arsenal"),
    )
    await session.flush()
    observation_id, team_id = observation.id, team.id
    module = importlib.import_module(
        "app.db.migrations.versions.20260911_0029_add_sms24_sporting_jurisdiction_and_safe_identity"
    )

    def round_trip(connection):
        with Operations.context(MigrationContext.configure(connection)):
            module.downgrade()
            module.upgrade()

    await (await session.connection()).run_sync(round_trip)
    session.expire_all()
    assert (await session.get(SportsCompetition, observation_id)).canonical_competition_id is None
    assert (await session.get(SportsCompetitor, team_id)).canonical_competitor_id is None
    assert await count(session, SportsCanonicalCompetition) == 1
    assert await count(session, SportsCanonicalCompetitor) == 1
    assert await count(session, SportsSeason) == 1
