"""0035 logical capability round trips in rollback-only disposable PostgreSQL schemas.

Reuse the 0034 fixture's explicit SMS24_MIGRATION_TEST_DATABASE_URL and schema
without public search-path fallback. No application DB or provider calls are used.
"""

import importlib
import uuid

import pytest
from sqlalchemy import insert

from app.models.sports_live import SportsDataSource, SportsDataSourceCapability
from tests import test_sms24_transfers_postgres as foundation
from tests.test_sms24_gnews_migration_postgres import rows

previous_connection = foundation.connection
MIGRATION = importlib.import_module(
    "app.db.migrations.versions.20260920_0035_enable_sportmonks_transfers"
)
SOURCES = SportsDataSource.__table__
CAPABILITIES = SportsDataSourceCapability.__table__


@pytest.fixture
async def connection(previous_connection):
    await previous_connection.run_sync(lambda sync: foundation.migrate(sync, foundation.M34))
    yield previous_connection


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
@pytest.mark.parametrize("api_transfers", [False, True])
@pytest.mark.parametrize("source_active", [False, True])
async def test_0035_upgrade_downgrade_reupgrade(
    connection,
    preexisting,
    api_transfers,
    source_active,
):
    assert MIGRATION.down_revision == foundation.M34.revision
    sportmonks_id = await seed_source(connection, "sportmonks", 47, source_active)
    api_id = await seed_source(connection, "api-football", 11, True)
    other_id = await seed_source(connection, "unrelated", 83)
    for source_id in (sportmonks_id, api_id):
        for capability in ("fixtures", "live", "standings"):
            await seed_capability(connection, source_id, capability, active=True)
    await seed_capability(connection, sportmonks_id, "news")
    await seed_capability(connection, other_id, "transfers", active=True)
    if api_transfers:
        await seed_capability(connection, api_id, "transfers")
    old_id = None
    if preexisting:
        old_id = await seed_capability(connection, sportmonks_id, "transfers")
        assert old_id != MIGRATION.SPORTMONKS_TRANSFERS_CAPABILITY_ID
    before_sources = await rows(connection, SOURCES)
    before_caps = [
        row
        for row in await rows(connection, CAPABILITIES)
        if not (row["source_id"] == sportmonks_id and row["capability"] == "transfers")
    ]

    for cycle in range(2):
        await connection.run_sync(lambda sync: foundation.migrate(sync, MIGRATION))
        caps = await rows(connection, CAPABILITIES)
        target = [
            row
            for row in caps
            if row["source_id"] == sportmonks_id and row["capability"] == "transfers"
        ]
        assert len(target) == 1
        assert target[0]["id"] == (
            old_id if preexisting and cycle == 0 else MIGRATION.SPORTMONKS_TRANSFERS_CAPABILITY_ID
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


async def test_0035_missing_sportmonks_is_noop(connection):
    api_id = await seed_source(connection, "api-football", 10)
    other_id = await seed_source(connection, "unrelated", 80)
    await seed_capability(connection, api_id, "fixtures", active=True)
    await seed_capability(connection, other_id, "transfers", active=True)
    before_sources = await rows(connection, SOURCES)
    before_caps = await rows(connection, CAPABILITIES)
    for direction in ("upgrade", "downgrade", "upgrade"):
        await connection.run_sync(
            lambda sync, direction=direction: foundation.migrate(sync, MIGRATION, direction)
        )
        assert await rows(connection, SOURCES) == before_sources
        assert await rows(connection, CAPABILITIES) == before_caps
