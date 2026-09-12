"""News persistence against actual 0031 DDL in isolated rollback-only schemas."""

import importlib
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.base import Base
from app.models.athlete import Athlete
from app.models.country import Country
from app.models.sport import Sport
from app.models.sports_live import (
    SportsCanonicalCompetition,
    SportsCanonicalCompetitor,
    SportsDataSource,
)
from app.models.sports_news import (
    SportsNewsArticle,
    SportsNewsArticleCompetition,
    SportsNewsArticleCompetitor,
    SportsNewsArticleCountry,
    SportsNewsArticleSport,
)
from app.sms24.news import SMS24NewsRepository
from app.sms24.providers.news import ProviderNewsResult
from tests.test_sms24_news_contract import NOW, article

MIGRATION = importlib.import_module(
    "app.db.migrations.versions.20260912_0031_add_sms24_news_foundation"
)
LINKS = (
    (SportsNewsArticleSport, "sport_id"),
    (SportsNewsArticleCompetition, "canonical_competition_id"),
    (SportsNewsArticleCompetitor, "canonical_competitor_id"),
    (SportsNewsArticleCountry, "country_id"),
)


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
                schema = f"sms24_news_test_{uuid.uuid4().hex}"
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                tables = [
                    model.__table__
                    for model in (
                        Sport,
                        Country,
                        SportsDataSource,
                        SportsCanonicalCompetition,
                        SportsCanonicalCompetitor,
                    )
                ]
                await connection.run_sync(
                    lambda conn: Base.metadata.create_all(conn, tables=tables)
                )
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


async def add(session, model, **values):
    item = model(**values)
    session.add(item)
    await session.flush()
    return item


async def seed(session):
    sources = [
        await add(
            session, SportsDataSource, slug=f"local-news-{i}", name="Local test", is_active=False
        )
        for i in range(2)
    ]
    sports = [
        await add(session, Sport, slug=slug, name=slug)
        for slug in ("football", "basketball", "athletics", "tennis")
    ]
    country = await add(session, Country, iso2="CI", iso3="CIV", name="Côte d'Ivoire")
    comp = await add(
        session,
        SportsCanonicalCompetition,
        sport_id=sports[0].id,
        name="League",
        normalized_name="league",
        canonical_key=uuid.uuid4().hex,
        jurisdiction_name="Scotland",
        identity_scope="provider_scoped",
    )
    teams = [
        await add(
            session,
            SportsCanonicalCompetitor,
            sport_id=sports[0].id,
            name="Same Name",
            normalized_name="same name",
            competitor_type=kind,
            identity_scope="provider_scoped",
            canonical_key=uuid.uuid4().hex,
        )
        for kind in ("team", "team", "athlete")
    ]
    return SimpleNamespace(
        sources=sources, sports=sports, country=country, competition=comp, teams=teams
    )


async def ingest(session, world, *articles, source=0, fetched_at=NOW):
    return await SMS24NewsRepository(session).ingest(
        source_id=world.sources[source].id,
        result=ProviderNewsResult(fetched_at=fetched_at, articles=articles),
    )


async def rows(session):
    return list(
        await session.scalars(select(SportsNewsArticle).execution_options(populate_existing=True))
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("sport_index", [0, 1, 2, 3])
async def test_each_sport_and_nullable_fields(session, sport_index):
    world = await seed(session)
    await ingest(session, world, article(sport_ids=(world.sports[sport_index].id,)))
    saved = (await rows(session))[0]
    assert saved.published_at is None and saved.excerpt is None and saved.language_code is None
    assert saved.fetched_at.utcoffset() is not None
    assert list(await session.scalars(select(SportsNewsArticleSport.sport_id))) == [
        world.sports[sport_index].id
    ]
    assert await session.scalar(select(func.count()).select_from(SportsNewsArticleCountry)) == 0
    assert all(not source.is_active for source in world.sources)


@pytest.mark.asyncio
async def test_idempotent_update_additive_links_and_stale_snapshot(session):
    world = await seed(session)
    first = article(external_id="42", excerpt="Source excerpt", sport_ids=(world.sports[0].id,))
    await ingest(session, world, first)
    saved_id = (await rows(session))[0].id
    result = await ingest(session, world, first)
    assert result.articles_upserted == 1 and len(await rows(session)) == 1
    update = article(
        external_id="42",
        title="Updated",
        source_url="https://news.test/new",
        sport_ids=(world.sports[1].id,),
        publication_status="published",
    )
    await ingest(session, world, update, fetched_at=NOW + timedelta(hours=1))
    saved = (await rows(session))[0]
    assert saved.id == saved_id and saved.title == "Updated" and saved.excerpt is None
    assert saved.source_url == "https://news.test/new" and saved.publication_status == "published"
    assert set(await session.scalars(select(SportsNewsArticleSport.sport_id))) == {
        s.id for s in world.sports[:2]
    }
    stale = await ingest(session, world, first)
    assert stale.articles_processed == 1 and stale.articles_upserted == 0
    assert (await rows(session))[0].title == "Updated"
    await ingest(session, world, article(external_id="42"), fetched_at=NOW + timedelta(hours=2))
    assert await session.scalar(select(func.count()).select_from(SportsNewsArticleSport)) == 2


@pytest.mark.asyncio
async def test_distinct_sources_and_titles_do_not_merge(session):
    world = await seed(session)
    for source in (0, 1):
        await ingest(session, world, article(external_id="42"), source=source)
    await ingest(session, world, article(external_id="43"))
    assert len(await rows(session)) == 3
    assert len({row.title for row in await rows(session)}) == 1


@pytest.mark.asyncio
async def test_url_fallback_idempotence_preserves_query(session):
    world = await seed(session)
    await ingest(session, world, article(source_url="https://news.test/a?story=1"))
    await ingest(session, world, article(source_url="HTTPS://NEWS.TEST/a?story=1#heading"))
    await ingest(session, world, article(source_url="https://news.test/a?story=2"))
    assert len(await rows(session)) == 2


@pytest.mark.asyncio
async def test_multisport_multiple_explicit_links_and_canonical_athlete(session):
    world = await seed(session)
    item = article(
        sport_ids=tuple(s.id for s in world.sports) * 2,
        canonical_competition_ids=(world.competition.id, world.competition.id),
        canonical_competitor_ids=tuple(t.id for t in world.teams) * 2,
        country_ids=(world.country.id, world.country.id),
    )
    await ingest(session, world, item)
    await ingest(session, world, item)
    for (model, _), count in zip(LINKS, (4, 1, 3, 1), strict=True):
        assert await session.scalar(select(func.count()).select_from(model)) == count
    assert set(
        await session.scalars(select(SportsNewsArticleCompetitor.canonical_competitor_id))
    ) == {t.id for t in world.teams}
    # The canonical athlete link succeeded without creating the user-profile Athlete table.
    connection = await session.connection()
    assert not await connection.run_sync(
        lambda conn: inspect(conn).has_table(Athlete.__tablename__)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("model,column", LINKS)
async def test_duplicate_association_rejected_by_database(session, model, column):
    world = await seed(session)
    await ingest(
        session,
        world,
        article(
            sport_ids=(world.sports[0].id,),
            canonical_competition_ids=(world.competition.id,),
            canonical_competitor_ids=(world.teams[0].id,),
            country_ids=(world.country.id,),
        ),
    )
    existing = (await session.scalars(select(model))).one()
    async with session.begin_nested() as savepoint:
        with pytest.raises(IntegrityError):
            await session.execute(
                model.__table__.insert().values(
                    article_id=existing.article_id, **{column: getattr(existing, column)}
                )
            )
        await savepoint.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    [
        "sport_ids",
        "country_ids",
        "canonical_competition_ids",
        "canonical_competitor_ids",
        "source_id",
    ],
)
async def test_invalid_foreign_keys_propagate_and_batch_rolls_back(session, field):
    world = await seed(session)
    with pytest.raises(IntegrityError):
        if field == "source_id":
            await SMS24NewsRepository(session).ingest(
                source_id=uuid.uuid4(),
                result=ProviderNewsResult(fetched_at=NOW, articles=(article(),)),
            )
        else:
            await ingest(session, world, article(**{field: (uuid.uuid4(),)}))
    assert await rows(session) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,target",
    [("canonical_competition_ids", "competition"), ("canonical_competitor_ids", "team")],
)
async def test_cross_sport_link_rejected_without_partial_writes(session, field, target):
    world = await seed(session)
    identity = world.competition.id if target == "competition" else world.teams[0].id
    with pytest.raises(ValueError, match="incompatible sport"):
        await ingest(
            session,
            world,
            article(external_id="valid"),
            article(sport_ids=(world.sports[1].id,), **{field: (identity,)}),
        )
    assert await rows(session) == []


@pytest.mark.asyncio
async def test_no_country_inferred_from_competition_jurisdiction(session):
    world = await seed(session)
    await ingest(
        session,
        world,
        article(sport_ids=(world.sports[0].id,), canonical_competition_ids=(world.competition.id,)),
    )
    assert await session.scalar(select(func.count()).select_from(SportsNewsArticleCountry)) == 0


@pytest.mark.asyncio
async def test_caller_rollback_and_no_internal_commit(session):
    world = await seed(session)
    await session.commit()  # Only a savepoint within this test's outer rollback transaction.
    session.commit = AsyncMock(side_effect=AssertionError("Internal commit forbidden"))
    await ingest(session, world, article(sport_ids=(world.sports[0].id,)))
    assert len(await rows(session)) == 1
    session.commit.assert_not_awaited()
    await session.rollback()
    assert await rows(session) == []
    assert await session.scalar(select(func.count()).select_from(SportsNewsArticleSport)) == 0


@pytest.mark.asyncio
async def test_publication_requires_explicit_sport(session):
    world = await seed(session)
    with pytest.raises(ValueError, match="explicit sport"):
        await ingest(session, world, article(publication_status="published"))
    assert await rows(session) == []


@pytest.mark.asyncio
async def test_migration_upgrade_downgrade_reupgrade(session):
    world = await seed(session)
    await ingest(session, world, article(sport_ids=(world.sports[0].id,)))
    connection = await session.connection()
    await connection.run_sync(lambda conn: migrate(conn, "downgrade"))
    assert not await connection.run_sync(
        lambda conn: inspect(conn).has_table("sports_news_articles")
    )
    assert await session.scalar(select(func.count()).select_from(Sport)) == 4
    await connection.run_sync(lambda conn: migrate(conn, "upgrade"))
    await ingest(session, world, article(sport_ids=(world.sports[3].id,)))
    assert len(await rows(session)) == 1
    assert set(SportsNewsArticle.__table__.columns.keys()) == set(
        await connection.run_sync(
            lambda conn: [
                column["name"] for column in inspect(conn).get_columns("sports_news_articles")
            ]
        )
    )
