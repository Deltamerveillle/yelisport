"""Standings ingestion and reversible migration tests in per-test PostgreSQL schemas."""

import importlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.base import Base
from app.models.sport import Sport
from app.models.sports_live import (
    SportsCanonicalCompetition,
    SportsCanonicalCompetitor,
    SportsCompetition,
    SportsCompetitor,
    SportsDataSource,
    SportsSeason,
)
from app.models.sports_standings import SportsStanding
from app.sms24.ingestion import SMS24IngestionRepository
from app.sms24.providers import (
    ProviderCompetition,
    ProviderParticipant,
    ProviderStanding,
    ProviderStandingsResult,
)
from app.sms24.standings import SMS24StandingsRepository

NOW = datetime(2026, 9, 11, 12, tzinfo=UTC)
MIGRATION = importlib.import_module("app.db.migrations.versions.20260911_0030_add_sms24_standings")


def migrate(connection, direction):
    with Operations.context(MigrationContext.configure(connection)):
        getattr(MIGRATION, direction)()


@pytest.fixture
async def session():
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                schema = f"sms24_standings_test_{uuid.uuid4().hex}"
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                tables = [
                    model.__table__
                    for model in (
                        Sport,
                        SportsDataSource,
                        SportsCanonicalCompetition,
                        SportsCanonicalCompetitor,
                        SportsSeason,
                        SportsCompetition,
                        SportsCompetitor,
                    )
                ]
                await connection.run_sync(
                    lambda conn: Base.metadata.create_all(conn, tables=tables)
                )
                # Test against the actual 0030 DDL, not just ORM-generated standings DDL.
                await connection.run_sync(lambda conn: migrate(conn, "upgrade"))
                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as test_session:
                    yield test_session
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


async def seed(session):
    sport = Sport(slug="football", name="Football")
    sources = [SportsDataSource(slug=slug, name=slug) for slug in ("api-football", "sportmonks")]
    session.add_all([sport, *sources])
    await session.flush()
    identities = SMS24IngestionRepository(session)
    competition = await identities.resolve_canonical_competition(
        source_id=sources[0].id,
        sport_id=sport.id,
        competition=ProviderCompetition(
            external_id="7", name="League", jurisdiction_name="England"
        ),
    )
    season = await identities.resolve_season(
        canonical_competition_id=competition.id, label="2026/27"
    )
    return sport, sources, season


def row(external="42", name="Arsenal", **kwargs):
    return ProviderStanding(
        participant=ProviderParticipant(external_id=external, name=name), position=1, **kwargs
    )


async def ingest(session, source, season, rows, fetched_at=NOW):
    return await SMS24StandingsRepository(session).ingest(
        source_id=source.id,
        season_id=season.id,
        result=ProviderStandingsResult(rows=rows, fetched_at=fetched_at),
    )


async def observations(session):
    return list(
        (
            await session.scalars(select(SportsStanding).execution_options(populate_existing=True))
        ).all()
    )


@pytest.mark.asyncio
async def test_repeated_null_context_updates_one_observation_and_clears_missing_values(session):
    _, sources, season = await seed(session)
    first = await ingest(session, sources[0], season, [row(points=9, played=4, form="WWWL")])
    assert first.rows_processed == first.rows_upserted == 1
    stored = (await observations(session))[0]
    original_id = stored.id
    await ingest(session, sources[0], season, [row(points=10)], NOW + timedelta(minutes=5))
    rows = await observations(session)
    assert len(rows) == 1 and rows[0].id == original_id
    assert rows[0].points == 10 and rows[0].played is None and rows[0].form is None
    assert rows[0].home_points is None and rows[0].away_points is None
    assert rows[0].fetched_at == NOW + timedelta(minutes=5)
    assert rows[0].stage_external_id is None and rows[0].group_scope == "none:"
    assert await session.scalar(select(func.count()).select_from(SportsCanonicalCompetitor)) == 1
    # Verify the database itself rejects duplicate NULL scope even without our UPSERT.
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                insert(SportsStanding).values(
                    source_id=sources[0].id,
                    season_id=season.id,
                    canonical_competitor_id=rows[0].canonical_competitor_id,
                    position=2,
                    fetched_at=NOW,
                )
            )


@pytest.mark.asyncio
async def test_stage_group_scopes_and_metadata_are_preserved(session):
    _, sources, season = await seed(session)
    await ingest(
        session,
        sources[0],
        season,
        [
            row(group_name="Group A"),
            row(group_name="Group B"),
            row(stage_external_id="s1", group_external_id="g1", group_name="Group A"),
            row(stage_external_id="s2", group_external_id="g1", group_name="Group A"),
            row(group_external_id="Group A"),
        ],
    )
    assert len(await observations(session)) == 5
    await ingest(
        session,
        sources[0],
        season,
        [
            row(
                stage_external_id="s1",
                group_external_id="g1",
                group_name="Renamed group",
                external_id="standing/1",
                external_competition_id="7",
                external_season_id="88",
                round_external_id="round/2",
                standing_rule_external_id="rule:A",
                points=12,
                home_points=7,
                away_points=5,
                provider_updated_at=NOW,
            )
        ],
    )
    rows = await observations(session)
    assert len(rows) == 5
    stored = next(item for item in rows if item.stage_external_id == "s1")
    assert stored.group_name == "Renamed group" and stored.group_scope == "id:g1"
    assert (stored.external_id, stored.external_competition_id, stored.external_season_id) == (
        "standing/1",
        "7",
        "88",
    )
    assert (stored.round_external_id, stored.standing_rule_external_id) == ("round/2", "rule:A")
    assert (stored.home_points, stored.away_points, stored.provider_updated_at) == (7, 5, NOW)


@pytest.mark.asyncio
async def test_two_sources_preserve_separate_observations_for_existing_shared_canonical(session):
    sport, sources, season = await seed(session)
    identities = SMS24IngestionRepository(session)
    competitors = []
    for source in sources:
        competitors.append(
            await identities.upsert_competitor(
                source_id=source.id,
                sport_id=sport.id,
                fetched_at=NOW,
                participant=ProviderParticipant(
                    external_id="42", name="Arsenal", country_code="GB", short_name="ARS"
                ),
            )
        )
    assert competitors[0].canonical_competitor_id == competitors[1].canonical_competitor_id
    for source in sources:
        await ingest(session, source, season, [row()])
    rows = await observations(session)
    assert len(rows) == 2 and rows[0].source_id != rows[1].source_id
    assert rows[0].canonical_competitor_id == rows[1].canonical_competitor_id
    for competitor in competitors:
        await session.refresh(competitor)
        assert competitor.country_code == "GB" and competitor.short_name == "ARS"


@pytest.mark.asyncio
async def test_no_name_fuzzy_or_cross_source_merge_and_seasons_remain_distinct(session):
    _, sources, season = await seed(session)
    await ingest(
        session,
        sources[0],
        season,
        [row(), row("9419"), row("psg", "PSG"), row("paris", "Paris Saint-Germain")],
    )
    await ingest(session, sources[1], season, [row()])
    rows = await observations(session)
    assert len({item.canonical_competitor_id for item in rows}) == 5
    next_season = await SMS24IngestionRepository(session).resolve_season(
        canonical_competition_id=season.canonical_competition_id,
        label="2027/28",
    )
    await ingest(session, sources[0], next_season, [row()])
    assert len(await observations(session)) == 6
    assert await session.scalar(select(func.count()).select_from(SportsCanonicalCompetitor)) == 5


@pytest.mark.asyncio
async def test_caller_rollback_removes_standings_and_new_canonical_entities(session):
    _, sources, season = await seed(session)
    await session.commit()
    await ingest(session, sources[0], season, [row()])
    assert len(await observations(session)) == 1
    await session.rollback()
    assert await observations(session) == []
    assert await session.scalar(select(func.count()).select_from(SportsCanonicalCompetitor)) == 0
    assert await session.scalar(select(func.count()).select_from(SportsSeason)) == 1


@pytest.mark.asyncio
async def test_unlinked_competitor_reuses_identity_resolver_without_overwriting_observation(
    session,
):
    sport, sources, season = await seed(session)
    competitor = SportsCompetitor(
        source_id=sources[0].id,
        sport_id=sport.id,
        external_id="42",
        name="Arsenal",
        short_name="ARS",
        country_code="GB",
        metadata_json={"preserve": True},
    )
    session.add(competitor)
    await session.flush()
    await ingest(session, sources[0], season, [row()])
    await session.refresh(competitor)
    assert (
        competitor.canonical_competitor_id
        == (await observations(session))[0].canonical_competitor_id
    )
    assert competitor.metadata_json == {"preserve": True} and competitor.short_name == "ARS"


@pytest.mark.asyncio
async def test_invalid_contract_mixed_seasons_and_unknown_season_fail_conservatively(session):
    _, sources, season = await seed(session)
    bad = row()
    bad.position = 0
    with pytest.raises(ValueError, match="position"):
        await ingest(session, sources[0], season, [bad])
    with pytest.raises(ValueError, match="mixed"):
        await ingest(
            session,
            sources[0],
            season,
            [row(external_season_id="88"), row(external_season_id="99")],
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        await ingest(session, sources[0], season, [row()], NOW.replace(tzinfo=None))
    with pytest.raises(ValueError, match="existing"):
        await SMS24StandingsRepository(session).ingest(
            source_id=sources[0].id,
            season_id=uuid.uuid4(),
            result=ProviderStandingsResult(rows=[row()], fetched_at=NOW),
        )
    assert await observations(session) == []


@pytest.mark.asyncio
async def test_cross_sport_competitor_is_rejected(session):
    _, sources, season = await seed(session)
    sport = Sport(slug="tennis", name="Tennis")
    session.add(sport)
    await session.flush()
    session.add(
        SportsCompetitor(
            source_id=sources[0].id, sport_id=sport.id, external_id="42", name="Arsenal"
        )
    )
    await session.flush()
    with pytest.raises(ValueError, match="different sport"):
        await ingest(session, sources[0], season, [row()])
    assert await observations(session) == []


@pytest.mark.asyncio
async def test_migration_downgrade_reupgrade_keeps_parent_entities(session):
    _, sources, season = await seed(session)
    await ingest(session, sources[0], season, [row()])
    connection = await session.connection()
    await connection.run_sync(lambda conn: migrate(conn, "downgrade"))
    assert await session.scalar(text("SELECT to_regclass('sports_standings')")) is None
    assert await session.scalar(select(func.count()).select_from(SportsSeason)) == 1
    await connection.run_sync(lambda conn: migrate(conn, "upgrade"))
    assert await observations(session) == []


@pytest.mark.asyncio
async def test_group_label_case_and_outer_whitespace_share_scope_without_losing_display(session):
    _, sources, season = await seed(session)
    original_id = None
    for index, label in enumerate(["Group A", " group a ", "GROUP A", "\tGrOuP A\r\n"]):
        await ingest(session, sources[0], season, [row(group_name=label, points=index)])
        rows = await observations(session)
        assert len(rows) == 1
        if original_id is None:
            original_id = rows[0].id
        assert rows[0].id == original_id
        assert rows[0].group_scope == "name:group a"
        assert rows[0].group_name == label
        assert rows[0].points == index
    # Scope matching is limited to case and outer whitespace, not fuzzy matching.
    await ingest(
        session, sources[0], season, [row(group_name="Group-A"), row(group_name="Group  A")]
    )
    assert len(await observations(session)) == 3
    # Provider IDs remain opaque and take precedence over any supplied display label.
    for label in ["Group A", "Other Group"]:
        await ingest(
            session, sources[0], season, [row(group_external_id="Group A", group_name=label)]
        )
    rows = await observations(session)
    assert len(rows) == 4
    identified = next(item for item in rows if item.group_external_id is not None)
    assert identified.group_scope == "id:Group A"
    assert identified.group_name == "Other Group"
