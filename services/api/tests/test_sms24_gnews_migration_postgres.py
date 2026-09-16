"""0033 round trips in rollback-only schemas on an explicit disposable PostgreSQL DB.

Set SMS24_MIGRATION_TEST_DATABASE_URL to a disposable database; application
settings and provider credentials are deliberately never read by this module.
"""

import importlib
import os
import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.models.sports_live import SportsDataSource, SportsDataSourceCapability

PREVIOUS = importlib.import_module(
    "app.db.migrations.versions.20260912_0032_add_sms24_source_capabilities"
)
MIGRATION = importlib.import_module(
    "app.db.migrations.versions.20260913_0033_seed_gnews_news_source"
)
SOURCES = SportsDataSource.__table__
CAPABILITIES = SportsDataSourceCapability.__table__


def migrate(connection, migration, direction):
    with Operations.context(MigrationContext.configure(connection)):
        getattr(migration, direction)()


@pytest.fixture
async def connection():
    url = os.environ.get("SMS24_MIGRATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("SMS24_MIGRATION_TEST_DATABASE_URL must name a disposable PostgreSQL DB")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                schema = f"sms24_0033_test_{uuid.uuid4().hex}"
                await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                # No public fallback: missing test tables cannot resolve to real tables.
                await conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                await conn.run_sync(lambda sync: SOURCES.create(sync))
                await conn.run_sync(lambda sync: migrate(sync, PREVIOUS, "upgrade"))
                yield conn
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


async def rows(connection, table):
    result = await connection.execute(select(table).order_by(table.c.id))
    return [dict(row) for row in result.mappings()]


@pytest.mark.parametrize("existing", ["none", "source", "capability"])
async def test_0033_upgrade_downgrade_reupgrade(connection, existing):
    assert MIGRATION.down_revision == PREVIOUS.revision
    other_id = uuid.uuid4()
    await connection.execute(insert(SOURCES).values(id=other_id, slug="unrelated", name="Other"))
    unrelated_cap_id = uuid.uuid4()
    await connection.execute(insert(CAPABILITIES).values(
        id=unrelated_cap_id, source_id=other_id, capability="news", priority=71,
    ))
    source_id = MIGRATION.GNEWS_SOURCE_ID if existing == "none" else uuid.uuid4()
    old_cap_id = uuid.uuid4()
    if existing != "none":
        await connection.execute(insert(SOURCES).values(
            id=source_id, slug="gnews", name="Old name", provider_type="rss",
            priority=88, is_active=False, health_status="degraded",
        ))
        await connection.execute(insert(CAPABILITIES).values(
            id=uuid.uuid4(), source_id=source_id, capability="fixtures", priority=82,
        ))
    if existing == "capability":
        await connection.execute(insert(CAPABILITIES).values(
            id=old_cap_id, source_id=source_id, capability="news",
            priority=93, is_active=False,
        ))
    untouched_sources = [r for r in await rows(connection, SOURCES) if r["id"] != source_id]
    untouched_caps = [
        r for r in await rows(connection, CAPABILITIES)
        if not (r["source_id"] == source_id and r["capability"] == "news")
    ]

    for cycle in range(2):
        await connection.run_sync(lambda sync: migrate(sync, MIGRATION, "upgrade"))
        source = next(r for r in await rows(connection, SOURCES) if r["id"] == source_id)
        assert (source["slug"], source["name"], source["provider_type"], source["priority"]) == (
            "gnews", "GNews", "api", 30,
        )
        assert source["is_active"] is (existing == "none")
        assert source["health_status"] == ("unavailable" if existing == "none" else "degraded")
        caps = await rows(connection, CAPABILITIES)
        news = [r for r in caps if r["source_id"] == source_id and r["capability"] == "news"]
        assert len(news) == 1
        assert news[0]["id"] == (
            old_cap_id if existing == "capability" and cycle == 0
            else MIGRATION.GNEWS_NEWS_CAPABILITY_ID
        )
        assert news[0]["priority"] == 30
        assert news[0]["is_active"] is True
        assert [r for r in caps if r not in news] == untouched_caps
        # Repeated upgrade must leave IDs, timestamps, and row counts unchanged.
        await connection.run_sync(lambda sync: migrate(sync, MIGRATION, "upgrade"))
        assert await rows(connection, CAPABILITIES) == caps
        await connection.run_sync(lambda sync: migrate(sync, MIGRATION, "downgrade"))
        assert await rows(connection, CAPABILITIES) == untouched_caps
        remaining = await rows(connection, SOURCES)
        assert next(r for r in remaining if r["id"] == source_id) == source
        assert [r for r in remaining if r["id"] != source_id] == untouched_sources
