"""0038 logical capability round trips in rollback-only disposable PostgreSQL schemas.

Reuse the foundation fixtures' explicit SMS24_MIGRATION_TEST_DATABASE_URL and schema
without public search-path fallback. No application DB or provider calls are used.
"""

import importlib
import uuid

import pytest
from sqlalchemy import insert

from app.models.sports_live import SportsDataSource, SportsDataSourceCapability
from tests import test_sms24_player_statistics_postgres as statistics_foundation
from tests import test_sms24_transfers_postgres as foundation
from tests.test_sms24_gnews_migration_postgres import rows

previous_connection = statistics_foundation.previous_connection
statistics_connection = statistics_foundation.connection
MIGRATION = importlib.import_module(
    "app.db.migrations.versions.20260922_0038_enable_sportmonks_player_statistics"
)
SOURCES = SportsDataSource.__table__
CAPABILITIES = SportsDataSourceCapability.__table__


@pytest.fixture
async def connection(statistics_connection):
    await statistics_connection.run_sync(
        lambda sync: foundation.migrate(sync, statistics_foundation.M37)
    )
    yield statistics_connection


async def seed_source(connection, slug, priority, active=False):
    source_id = uuid.uuid4()  # Deliberately unrelated to the source seed UUIDs.
    await connection.execute(
        insert(SOURCES).values(
            id=source_id,
            slug=slug,
            name=f"Existing {slug}",
            priority=priority,
            is_active=active,
            health_status="degraded",
            last_success_at=foundation.NOW,
            last_failure_at=foundation.NOW,
            last_checked_at=foundation.NOW,
        )
    )
    return source_id


async def seed_capability(connection, source_id, capability, priority=79, active=False):
    identity = uuid.uuid4()
    await connection.execute(
        insert(CAPABILITIES).values(
            id=identity,
            source_id=source_id,
            capability=capability,
            priority=priority,
            is_active=active,
        )
    )
    return identity


@pytest.mark.parametrize("preexisting", [False, True])
@pytest.mark.parametrize("api_statistics", [False, True])
@pytest.mark.parametrize("source_active", [False, True])
async def test_0038_upgrade_downgrade_reupgrade(
    connection,
    preexisting,
    api_statistics,
    source_active,
):
    assert MIGRATION.down_revision == statistics_foundation.M37.revision
    assert MIGRATION.revision == "20260922_0038"
    assert MIGRATION.SPORTMONKS_STATISTICS_CAPABILITY_ID == uuid.uuid5(
        uuid.NAMESPACE_URL, "sms24:source-capability:sportmonks:statistics"
    )
    sportmonks_id = await seed_source(connection, "sportmonks", 47, source_active)
    api_id = await seed_source(connection, "api-football", 11, True)
    other_id = await seed_source(connection, "unrelated", 83)
    for source_id in (sportmonks_id, api_id):
        for capability in ("fixtures", "live", "standings", "transfers"):
            await seed_capability(connection, source_id, capability, active=True)
    await seed_capability(connection, sportmonks_id, "news")
    await seed_capability(connection, other_id, "statistics", active=True)
    if api_statistics:
        await seed_capability(connection, api_id, "statistics")
    old_id = None
    if preexisting:
        old_id = await seed_capability(connection, sportmonks_id, "statistics")
        assert old_id != MIGRATION.SPORTMONKS_STATISTICS_CAPABILITY_ID
    before_sources = await rows(connection, SOURCES)
    before_caps = [
        row
        for row in await rows(connection, CAPABILITIES)
        if not (row["source_id"] == sportmonks_id and row["capability"] == "statistics")
    ]

    for cycle in range(2):
        await connection.run_sync(lambda sync: foundation.migrate(sync, MIGRATION))
        caps = await rows(connection, CAPABILITIES)
        target = [
            row
            for row in caps
            if row["source_id"] == sportmonks_id and row["capability"] == "statistics"
        ]
        assert len(target) == 1
        assert target[0]["id"] == (
            old_id if preexisting and cycle == 0 else MIGRATION.SPORTMONKS_STATISTICS_CAPABILITY_ID
        )
        assert target[0]["priority"] == 47
        assert target[0]["is_active"] is True
        assert [row for row in caps if row not in target] == before_caps
        assert await rows(connection, SOURCES) == before_sources
        # Repeated upgrade preserves IDs, timestamps and all unrelated rows.
        await connection.run_sync(lambda sync: foundation.migrate(sync, MIGRATION))
        assert await rows(connection, CAPABILITIES) == caps
        await connection.run_sync(lambda sync: foundation.migrate(sync, MIGRATION, "downgrade"))
        # Intentional 0033 convention: a pre-existing capability is removed too.
        assert await rows(connection, CAPABILITIES) == before_caps
        assert await rows(connection, SOURCES) == before_sources

    # Leave the final upgrade active inside the rollback-only test transaction.
    await connection.run_sync(lambda sync: foundation.migrate(sync, MIGRATION))
    assert len(await rows(connection, CAPABILITIES)) == len(before_caps) + 1
    assert await rows(connection, SOURCES) == before_sources


async def test_0038_missing_sportmonks_is_noop(connection):
    api_id = await seed_source(connection, "api-football", 10)
    other_id = await seed_source(connection, "unrelated", 80)
    await seed_capability(connection, api_id, "fixtures", active=True)
    await seed_capability(connection, other_id, "statistics", active=True)
    before_sources = await rows(connection, SOURCES)
    before_caps = await rows(connection, CAPABILITIES)
    for direction in ("upgrade", "downgrade", "upgrade"):
        await connection.run_sync(
            lambda sync, direction=direction: foundation.migrate(sync, MIGRATION, direction)
        )
        assert await rows(connection, SOURCES) == before_sources
        assert await rows(connection, CAPABILITIES) == before_caps
