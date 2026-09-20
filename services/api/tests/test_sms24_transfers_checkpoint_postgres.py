"""Checkpoint DDL, transaction boundaries and locks on the disposable test DB only."""

import asyncio
import importlib
import os
import uuid
from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.sms24_job import SMS24JobCheckpoint
from app.sms24.providers.transfers import ProviderTransfer
from app.sms24.transfers import SMS24TransfersRepository
from app.sms24.transfers_batch import (
    AutomaticTransfersCursor,
    AutomaticTransfersResult,
    TransfersBatchResult,
    TransfersTargetAttempt,
)
from app.sms24.transfers_checkpoint import (
    CheckpointLockNotAcquired,
    SMS24TransfersCheckpointRepository,
    checkpoint_lock_key,
)
from app.sms24.transfers_targets import TransfersDiscoveryAttempt, TransfersTargetDiscoveryResult
from tests import test_sms24_transfers_postgres as foundation
from tests.test_sms24_transfers_runner_postgres import forbid_http  # noqa: F401

M35 = importlib.import_module(
    "app.db.migrations.versions.20260920_0035_enable_sportmonks_transfers"
)
M36 = importlib.import_module("app.db.migrations.versions.20260920_0036_add_sms24_job_checkpoints")
previous_connection = foundation.connection
DAY = date(2026, 9, 20)


@pytest.fixture
async def connection(previous_connection):
    for migration in (foundation.M34, M35):
        await previous_connection.run_sync(lambda sync, m=migration: foundation.migrate(sync, m))
    yield previous_connection


@pytest.fixture
async def session(connection):
    await connection.run_sync(lambda sync: foundation.migrate(sync, M36))
    async with AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        async with session.begin():
            yield session


def result(cursor=None, *, failed=False, reason=None):
    return AutomaticTransfersResult(
        discovery=TransfersTargetDiscoveryResult(reason=reason),
        batch=TransfersBatchResult(
            targets_discovered=1,
            attempts=(TransfersTargetAttempt("112", not failed),),
        ),
        next_cursor=cursor,
    )


async def test_migration_roundtrip_preserves_existing_tables(connection):
    assert M36.down_revision == M35.revision

    def inspect_tables(sync):
        db = inspect(sync)
        return {
            name: (db.get_columns(name), db.get_indexes(name), db.get_check_constraints(name))
            for name in db.get_table_names()
            if name != SMS24JobCheckpoint.__tablename__
        }

    # Stringify types to compare independent SQLAlchemy reflection objects.
    before = str(await connection.run_sync(inspect_tables))
    source_rows = (await connection.execute(select(foundation.SportsDataSource))).all()
    caps = (await connection.execute(select(foundation.SportsDataSourceCapability))).all()
    for direction in ("upgrade", "downgrade", "upgrade"):
        await connection.run_sync(lambda sync, d=direction: foundation.migrate(sync, M36, d))
        assert str(await connection.run_sync(inspect_tables)) == before
        assert (await connection.execute(select(foundation.SportsDataSource))).all() == source_rows
        assert (
            await connection.execute(select(foundation.SportsDataSourceCapability))
        ).all() == caps
        names = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
        assert (SMS24JobCheckpoint.__tablename__ in names) == (direction == "upgrade")
    columns = await connection.run_sync(
        lambda sync: inspect(sync).get_columns(SMS24JobCheckpoint.__tablename__),
    )
    assert {c["name"]: c["nullable"] for c in columns} == {
        c.name: c.nullable for c in SMS24JobCheckpoint.__table__.c
    }


async def test_absent_create_read_unique(session):
    repo = SMS24TransfersCheckpointRepository(session)
    assert await repo.get() is None
    with pytest.raises(ValueError, match="No running"):
        await repo.save_progress(result(AutomaticTransfersCursor("62")))
    with pytest.raises(ValueError, match="No running"):
        await repo.complete_run(result())
    state = await repo.get_or_create()
    assert state.status == "idle" and state.cursor is None
    assert await repo.get_or_create() == state
    assert await repo.get() == state
    with pytest.raises(IntegrityError), session.no_autoflush:
        async with session.begin_nested():
            session.add(SMS24JobCheckpoint(job_key=state.job_key))
            await session.flush()


@pytest.mark.parametrize(
    "cursor", [AutomaticTransfersCursor("62"), AutomaticTransfersCursor("62", "112")]
)
async def test_progress_fixed_parameters_and_restart(session, cursor):
    repo = SMS24TransfersCheckpointRepository(session)
    started = await repo.start_run(reference_date=DAY, max_teams=3, max_players=7)
    assert started.cursor == AutomaticTransfersCursor()
    progressed = await repo.save_progress(result(cursor, failed=True))
    assert progressed.cursor == cursor and progressed.failed_attempts == 1
    assert (progressed.reference_date, progressed.max_teams, progressed.max_players) == (DAY, 3, 7)
    with pytest.raises(ValueError, match="already running"):
        await repo.start_run(reference_date=date(2026, 9, 21), max_teams=8)
    assert await repo.get() == progressed
    completed = await repo.complete_run(result())
    assert completed.status == "completed_with_errors"
    assert completed.completed_at is not None and completed.cursor is None
    assert completed.started_at == started.started_at
    with pytest.raises(ValueError, match="No running"):
        await repo.save_progress(result(cursor))
    restarted = await repo.start_run(reference_date=date(2026, 9, 21), max_teams=2, max_players=4)
    assert restarted.cursor == AutomaticTransfersCursor()
    assert restarted.failed_attempts == 0 and restarted.completed_at is None
    assert (restarted.reference_date, restarted.max_teams, restarted.max_players) == (
        date(2026, 9, 21),
        2,
        4,
    )
    assert restarted.created_at == started.created_at


@pytest.mark.parametrize(
    "reason",
    [
        "transfers_capability_not_active",
        "provider_not_registered",
        "target_discovery_not_supported",
    ],
)
async def test_unavailable_never_completes_or_advances(session, reason):
    repo = SMS24TransfersCheckpointRepository(session)
    before = await repo.start_run(reference_date=DAY)
    for method in (repo.complete_run, repo.save_progress):
        with pytest.raises(ValueError, match="Discovery unavailable"):
            await method(result(reason=reason))
    assert await repo.get() == before


async def test_completion_is_explicit_and_empty_success_is_valid(session):
    repo = SMS24TransfersCheckpointRepository(session)
    await repo.start_run(reference_date=DAY)
    empty = AutomaticTransfersResult(TransfersTargetDiscoveryResult(), TransfersBatchResult(0, ()))
    with pytest.raises(ValueError, match="explicit decision"):
        await repo.save_progress(empty)
    assert (await repo.get()).status == "running"
    done = await repo.complete_run(empty)
    assert done.status == "completed" and done.failed_attempts == 0


async def test_incomplete_result_cannot_complete_and_team_failures_are_retained(session):
    repo = SMS24TransfersCheckpointRepository(session)
    await repo.start_run(reference_date=DAY)
    page = replace(
        result(AutomaticTransfersCursor("62")),
        discovery=TransfersTargetDiscoveryResult(
            attempts=(TransfersDiscoveryAttempt("53", False, "discovery_payload_failed"),),
            teams_limited=True,
            next_cursor="62",
        ),
    )
    with pytest.raises(ValueError, match="still has"):
        await repo.complete_run(page)
    await repo.save_progress(page)
    with pytest.raises(ValueError, match="still has"):
        await repo.complete_run(replace(page, next_cursor=None))
    assert (await repo.complete_run(result())).status == "completed_with_errors"


@pytest.mark.parametrize(
    "values",
    [
        {"reference_date": "2026-09-20"},
        {"max_teams": 0},
        {"max_players": True},
        {"max_players": -1},
        {"max_teams": 1.5},
    ],
)
async def test_invalid_start_leaves_absent_checkpoint(session, values):
    repo = SMS24TransfersCheckpointRepository(session)
    with pytest.raises(ValueError):
        await repo.start_run(**{"reference_date": DAY, **values})
    assert await repo.get() is None


@pytest.fixture
async def durable_database():
    """Only commit-boundary tests need a committed, unique temporary schema.

    Reuse the existing migration DB opt-in and foundation setup. Never use the
    application's DATABASE_URL, and never include public in the search path.
    """
    url = os.environ.get("SMS24_MIGRATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set SMS24_MIGRATION_TEST_DATABASE_URL to a disposable PostgreSQL DB")
    engine = create_async_engine(url, poolclass=NullPool)
    schema = f"sms24_0036_test_{uuid.uuid4().hex}"
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            await conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            await conn.run_sync(
                lambda sync: foundation.Base.metadata.create_all(
                    sync,
                    tables=[
                        getattr(foundation, name).__table__
                        for name in (
                            "Sport",
                            "Country",
                            "User",
                            "Athlete",
                            "AthletePassport",
                            "AthleteCountryEligibility",
                            "SportsDataSource",
                            "SportsCanonicalCompetition",
                            "SportsCanonicalCompetitor",
                            "SportsSeason",
                            "SportsCompetitor",
                        )
                    ],
                )
            )
            for migration in (foundation.M32, foundation.M33, foundation.M34, M35, M36):
                await conn.run_sync(lambda sync, m=migration: foundation.migrate(sync, m))
        yield engine, schema
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


async def set_schema(session, schema):
    await session.execute(text(f'SET LOCAL search_path TO "{schema}"'))


@pytest.mark.parametrize("commit", [True, False])
async def test_observations_and_checkpoint_commit_or_rollback_together(durable_database, commit):
    engine, schema = durable_database
    async with AsyncSession(engine) as session:
        async with session.begin():
            await set_schema(session, schema)
            source = await foundation.add(
                session, foundation.SportsDataSource, slug="sportmonks", name="Sportmonks"
            )
            source_id = source.id
            repo = SMS24TransfersCheckpointRepository(session)
            await repo.start_run(reference_date=DAY)
            await repo.save_progress(result(AutomaticTransfersCursor("53")))
        transaction = await session.begin()
        await set_schema(session, schema)
        assert await repo.try_acquire_lock()
        await SMS24TransfersRepository(session).record_observation(
            source_id=source_id,
            transfer=ProviderTransfer(athlete_external_id="112", external_id="541407"),
            fetched_at=foundation.NOW,
        )
        await repo.save_progress(result(AutomaticTransfersCursor("62", "112")))
        if commit:
            await transaction.commit()
        else:
            await transaction.rollback()
    async with AsyncSession(engine) as reader, reader.begin():
        await set_schema(reader, schema)
        state = await SMS24TransfersCheckpointRepository(reader).get()
        assert state.cursor == (
            AutomaticTransfersCursor("62", "112") if commit else AutomaticTransfersCursor("53")
        )
        assert await foundation.count(reader, foundation.SportsTransferObservation) == int(commit)
        for model in (
            foundation.User,
            foundation.Athlete,
            foundation.SportsAthleteIdentityLink,
            foundation.SportsCanonicalTransfer,
        ):
            assert await foundation.count(reader, model) == 0


@pytest.mark.parametrize("release", ["commit", "rollback", "close", "invalidate"])
async def test_two_sessions_nonblocking_lock_and_release(durable_database, release):
    engine, schema = durable_database
    async with AsyncSession(engine) as first, AsyncSession(engine) as second:
        await first.begin()
        await second.begin()
        await set_schema(first, schema)
        await set_schema(second, schema)
        one = SMS24TransfersCheckpointRepository(first)
        two = SMS24TransfersCheckpointRepository(second)
        assert await one.try_acquire_lock()
        assert await one.try_acquire_lock()  # Reentrant in the same transaction.
        assert not await asyncio.wait_for(two.try_acquire_lock(), timeout=1)
        with pytest.raises(CheckpointLockNotAcquired):
            await asyncio.wait_for(two.get_or_create(), timeout=1)
        # Independent jobs can progress concurrently.
        assert await SMS24TransfersCheckpointRepository(
            second, job_key="sms24:other"
        ).try_acquire_lock()
        await getattr(first, release)()
        assert await asyncio.wait_for(two.try_acquire_lock(), timeout=1)
        await second.rollback()
        # Reusing a repository cannot reuse stale lock ownership after commit.
        await first.begin()
        assert await one.try_acquire_lock()
        await first.rollback()


async def test_lock_requires_outer_transaction_and_rejects_savepoint(durable_database):
    engine, _ = durable_database
    async with AsyncSession(engine) as session:
        repo = SMS24TransfersCheckpointRepository(session)
        with pytest.raises(RuntimeError, match="outer transaction"):
            await repo.try_acquire_lock()
        async with session.begin(), session.begin_nested():
            with pytest.raises(RuntimeError, match="savepoint"):
                await repo.try_acquire_lock()


def test_lock_key_stable_and_validated():
    import hashlib

    key = "sms24:sportmonks:transfers"
    expected = int.from_bytes(
        hashlib.sha256(
            b"sms24-job-checkpoint:v1:sms24:sportmonks:transfers",
        ).digest()[:8],
        "big",
        signed=True,
    )
    assert checkpoint_lock_key(key) == expected
    assert -(2**63) <= expected < 2**63
    for invalid in (None, "", " ", "x" * 161):
        with pytest.raises(ValueError):
            checkpoint_lock_key(invalid)
