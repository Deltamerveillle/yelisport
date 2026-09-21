"""Tests for the dedicated SMS24 automatic Transfers worker."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.sms24.transfers_batch import (
    AutomaticTransfersCursor,
    AutomaticTransfersResult,
    TransfersBatchResult,
    TransfersTargetAttempt,
)
from app.sms24.transfers_targets import TransfersTargetDiscoveryResult
from app.sms24.transfers_worker import (
    TransfersWorkerConfig,
    _config_from_env,
    _env_bool,
)
from tests import test_sms24_transfers_checkpoint_postgres as checkpoint_foundation

durable_database = checkpoint_foundation.durable_database

DAY = date(2026, 9, 20)


def isolated_session_factory(engine, schema):
    """Create independent sessions whose connections use only the test schema."""
    isolated_engine = create_async_engine(
        engine.url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": schema}},
    )
    return isolated_engine, async_sessionmaker(
        isolated_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def config(*, max_teams: int = 20, max_players: int = 100) -> TransfersWorkerConfig:
    return TransfersWorkerConfig(
        cycle_interval_seconds=21600,
        page_interval_seconds=60,
        retry_interval_seconds=300,
        lock_retry_seconds=60,
        max_teams=max_teams,
        max_players=max_players,
    )


def result(
    cursor: AutomaticTransfersCursor | None = None,
    *,
    failed: bool = False,
    reason: str | None = None,
) -> AutomaticTransfersResult:
    return AutomaticTransfersResult(
        discovery=TransfersTargetDiscoveryResult(reason=reason),
        batch=TransfersBatchResult(
            targets_discovered=1,
            attempts=(
                TransfersTargetAttempt(
                    athlete_external_id="112",
                    success=not failed,
                ),
            ),
        ),
        next_cursor=cursor,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", True),
        ("true", True),
        ("YES", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("NO", False),
        ("off", False),
    ],
)
def test_env_bool_accepts_explicit_boolean_values(monkeypatch, raw, expected):
    monkeypatch.setenv("SMS24_TEST_BOOL", raw)
    assert _env_bool("SMS24_TEST_BOOL") is expected


def test_env_bool_rejects_invalid_value(monkeypatch):
    monkeypatch.setenv("SMS24_TEST_BOOL", "maybe")
    with pytest.raises(ValueError, match="must be a boolean"):
        _env_bool("SMS24_TEST_BOOL")


def test_env_bool_uses_default_when_unset(monkeypatch):
    monkeypatch.delenv("SMS24_TEST_BOOL", raising=False)
    assert _env_bool("SMS24_TEST_BOOL", True) is True
    assert _env_bool("SMS24_TEST_BOOL", False) is False


@pytest.mark.parametrize("value", ["0", "-1", "abc", "1.5"])
def test_worker_config_rejects_invalid_positive_integers(monkeypatch, value):
    monkeypatch.setenv("SMS24_TRANSFERS_MAX_PLAYERS", value)
    with pytest.raises(ValueError, match="positive integer"):
        _config_from_env()


async def test_first_iteration_starts_traversal_and_saves_progress(
    monkeypatch,
    durable_database,
):
    from app.sms24 import transfers_worker as worker

    engine, schema = durable_database
    isolated_engine, factory = isolated_session_factory(engine, schema)
    seen = {}

    async def fake_run(
        received_session,
        *,
        reference_date,
        settings,
        max_teams,
        max_players,
        cursor,
    ):
        seen.update(
            reference_date=reference_date,
            settings=settings,
            max_teams=max_teams,
            max_players=max_players,
            cursor=cursor,
        )
        return result(AutomaticTransfersCursor("62", "112"))

    monkeypatch.setattr(worker, "SessionFactory", factory)
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(worker, "run_sms24_automatic_transfers", fake_run)

    iteration = await worker._run_iteration(config(max_teams=3, max_players=7))

    assert iteration.state == "progress"
    assert seen["max_teams"] == 3
    assert seen["max_players"] == 7
    assert seen["cursor"] == AutomaticTransfersCursor()

    async with factory() as reader:
        async with reader.begin():
            checkpoint = await checkpoint_foundation.SMS24TransfersCheckpointRepository(
                reader
            ).get()

    assert checkpoint.status == "running"
    assert checkpoint.reference_date == seen["reference_date"]
    assert checkpoint.max_teams == 3
    assert checkpoint.max_players == 7
    assert checkpoint.cursor == AutomaticTransfersCursor("62", "112")
    await isolated_engine.dispose()


async def test_resume_uses_checkpoint_parameters_not_current_config(
    monkeypatch,
    durable_database,
):
    from app.sms24 import transfers_worker as worker

    engine, schema = durable_database
    isolated_engine, factory = isolated_session_factory(engine, schema)

    async with factory() as setup_session:
        async with setup_session.begin():
            repo = checkpoint_foundation.SMS24TransfersCheckpointRepository(
                setup_session
            )
            await repo.start_run(reference_date=DAY, max_teams=2, max_players=4)
            await repo.save_progress(
                result(AutomaticTransfersCursor("62", "112"))
            )

    seen = {}

    async def fake_run(
        received_session,
        *,
        reference_date,
        settings,
        max_teams,
        max_players,
        cursor,
    ):
        seen.update(
            reference_date=reference_date,
            max_teams=max_teams,
            max_players=max_players,
            cursor=cursor,
        )
        return result(AutomaticTransfersCursor("62", "200"))

    monkeypatch.setattr(worker, "SessionFactory", factory)
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(worker, "run_sms24_automatic_transfers", fake_run)

    iteration = await worker._run_iteration(config(max_teams=99, max_players=99))

    assert iteration.state == "progress"
    assert seen == {
        "reference_date": DAY,
        "max_teams": 2,
        "max_players": 4,
        "cursor": AutomaticTransfersCursor("62", "112"),
    }

    async with factory() as reader:
        async with reader.begin():
            checkpoint = await checkpoint_foundation.SMS24TransfersCheckpointRepository(
                reader
            ).get()

    assert checkpoint.max_teams == 2
    assert checkpoint.max_players == 4
    assert checkpoint.cursor == AutomaticTransfersCursor("62", "200")
    await isolated_engine.dispose()



@pytest.mark.parametrize(
    ("failed", "expected_state"),
    [
        (False, "completed"),
        (True, "completed_with_errors"),
    ],
)
async def test_terminal_iteration_completes_traversal(
    monkeypatch,
    durable_database,
    failed,
    expected_state,
):
    from app.sms24 import transfers_worker as worker

    engine, schema = durable_database
    isolated_engine, factory = isolated_session_factory(engine, schema)

    async def fake_run(
        received_session,
        *,
        reference_date,
        settings,
        max_teams,
        max_players,
        cursor,
    ):
        return result(failed=failed)

    monkeypatch.setattr(worker, "SessionFactory", factory)
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(worker, "run_sms24_automatic_transfers", fake_run)

    try:
        iteration = await worker._run_iteration(config(max_teams=3, max_players=7))

        assert iteration.state == expected_state
        assert iteration.targets_attempted == 1
        assert iteration.targets_failed == int(failed)

        async with factory() as reader:
            async with reader.begin():
                checkpoint = (
                    await checkpoint_foundation.SMS24TransfersCheckpointRepository(
                        reader
                    ).get()
                )

        assert checkpoint.status == expected_state
        assert checkpoint.cursor is None
        assert checkpoint.completed_at is not None
        assert checkpoint.max_teams == 3
        assert checkpoint.max_players == 7
        assert checkpoint.failed_attempts == int(failed)
    finally:
        await isolated_engine.dispose()


async def test_discovery_unavailable_rolls_back_without_advancing_checkpoint(
    monkeypatch,
    durable_database,
):
    from app.sms24 import transfers_worker as worker

    engine, schema = durable_database
    isolated_engine, factory = isolated_session_factory(engine, schema)
    original_cursor = AutomaticTransfersCursor("62", "112")

    try:
        async with factory() as setup_session:
            async with setup_session.begin():
                repo = checkpoint_foundation.SMS24TransfersCheckpointRepository(
                    setup_session
                )
                await repo.start_run(
                    reference_date=DAY,
                    max_teams=2,
                    max_players=4,
                )
                await repo.save_progress(result(original_cursor))

        async def fake_run(
            received_session,
            *,
            reference_date,
            settings,
            max_teams,
            max_players,
            cursor,
        ):
            assert reference_date == DAY
            assert max_teams == 2
            assert max_players == 4
            assert cursor == original_cursor
            return result(
                AutomaticTransfersCursor("62", "200"),
                reason="transfers_capability_not_active",
            )

        monkeypatch.setattr(worker, "SessionFactory", factory)
        monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace())
        monkeypatch.setattr(worker, "run_sms24_automatic_transfers", fake_run)

        with pytest.raises(RuntimeError, match="Transfers discovery unavailable"):
            await worker._run_iteration(config(max_teams=99, max_players=99))

        async with factory() as reader:
            async with reader.begin():
                checkpoint = (
                    await checkpoint_foundation.SMS24TransfersCheckpointRepository(
                        reader
                    ).get()
                )

        assert checkpoint.status == "running"
        assert checkpoint.reference_date == DAY
        assert checkpoint.max_teams == 2
        assert checkpoint.max_players == 4
        assert checkpoint.cursor == original_cursor
        assert checkpoint.completed_at is None
        assert checkpoint.failed_attempts == 0
    finally:
        await isolated_engine.dispose()


async def test_lock_busy_skips_ingestion_and_checkpoint_advance(
    monkeypatch,
    durable_database,
):
    from app.sms24 import transfers_worker as worker

    engine, schema = durable_database
    isolated_engine, factory = isolated_session_factory(engine, schema)
    ingestion_called = False

    async def fake_run(*args, **kwargs):
        nonlocal ingestion_called
        ingestion_called = True
        raise AssertionError("ingestion must not run while checkpoint lock is busy")

    monkeypatch.setattr(worker, "SessionFactory", factory)
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(worker, "run_sms24_automatic_transfers", fake_run)

    try:
        async with factory() as lock_session:
            async with lock_session.begin():
                lock_repo = (
                    checkpoint_foundation.SMS24TransfersCheckpointRepository(
                        lock_session
                    )
                )
                assert await lock_repo.try_acquire_lock() is True

                iteration = await worker._run_iteration(config())

                assert iteration.state == "lock_busy"
                assert ingestion_called is False

        # The competing transaction has now released the advisory lock.
        # Only then can the repository safely inspect the checkpoint.
        async with factory() as reader:
            async with reader.begin():
                checkpoint = (
                    await checkpoint_foundation
                    .SMS24TransfersCheckpointRepository(reader)
                    .get()
                )

        assert checkpoint is None
    finally:
        await isolated_engine.dispose()


async def test_completed_checkpoint_waits_for_remaining_cycle(
    monkeypatch,
    durable_database,
):
    from app.sms24 import transfers_worker as worker

    engine, schema = durable_database
    isolated_engine, factory = isolated_session_factory(engine, schema)
    ingestion_called = False

    async def fake_run(*args, **kwargs):
        nonlocal ingestion_called
        ingestion_called = True
        raise AssertionError("ingestion must not run before cycle is due")

    monkeypatch.setattr(worker, "SessionFactory", factory)
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(worker, "run_sms24_automatic_transfers", fake_run)

    try:
        async with factory() as setup_session:
            async with setup_session.begin():
                repo = checkpoint_foundation.SMS24TransfersCheckpointRepository(
                    setup_session
                )
                await repo.start_run(
                    reference_date=DAY,
                    max_teams=2,
                    max_players=4,
                )
                await repo.complete_run(result())

        iteration = await worker._run_iteration(config())

        assert iteration.state == "waiting_cycle"
        assert ingestion_called is False
        assert iteration.retry_after_seconds is not None
        assert 0 < iteration.retry_after_seconds <= 21600

        async with factory() as reader:
            async with reader.begin():
                checkpoint = (
                    await checkpoint_foundation.SMS24TransfersCheckpointRepository(
                        reader
                    ).get()
                )

        assert checkpoint.status == "completed"
        assert checkpoint.reference_date == DAY
        assert checkpoint.cursor is None
        assert checkpoint.completed_at is not None
    finally:
        await isolated_engine.dispose()


async def test_expired_completed_checkpoint_starts_new_traversal_with_current_config(
    monkeypatch,
    durable_database,
):
    from app.sms24 import transfers_worker as worker

    engine, schema = durable_database
    isolated_engine, factory = isolated_session_factory(engine, schema)
    current_day = datetime.now(UTC).date()
    new_cursor = AutomaticTransfersCursor("100", "200")
    received = {}

    try:
        async with factory() as setup_session:
            async with setup_session.begin():
                repo = checkpoint_foundation.SMS24TransfersCheckpointRepository(
                    setup_session
                )
                await repo.start_run(
                    reference_date=DAY,
                    max_teams=2,
                    max_players=4,
                )
                await repo.complete_run(result())

                row = await repo._read()
                assert row is not None
                row.completed_at = datetime.now(UTC) - timedelta(hours=7)

        async def fake_run(
            received_session,
            *,
            reference_date,
            settings,
            max_teams,
            max_players,
            cursor,
        ):
            received["reference_date"] = reference_date
            received["max_teams"] = max_teams
            received["max_players"] = max_players
            received["cursor"] = cursor
            return result(new_cursor)

        monkeypatch.setattr(worker, "SessionFactory", factory)
        monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace())
        monkeypatch.setattr(worker, "run_sms24_automatic_transfers", fake_run)

        iteration = await worker._run_iteration(
            config(max_teams=9, max_players=11)
        )

        assert iteration.state == "progress"
        assert received == {
            "reference_date": current_day,
            "max_teams": 9,
            "max_players": 11,
            "cursor": AutomaticTransfersCursor(),
        }

        async with factory() as reader:
            async with reader.begin():
                checkpoint = (
                    await checkpoint_foundation.SMS24TransfersCheckpointRepository(
                        reader
                    ).get()
                )

        assert checkpoint.status == "running"
        assert checkpoint.reference_date == current_day
        assert checkpoint.max_teams == 9
        assert checkpoint.max_players == 11
        assert checkpoint.cursor == new_cursor
        assert checkpoint.completed_at is None
    finally:
        await isolated_engine.dispose()


async def test_unexpected_ingestion_error_rolls_back_without_advancing_checkpoint(
    monkeypatch,
    durable_database,
):
    from app.sms24 import transfers_worker as worker

    engine, schema = durable_database
    isolated_engine, factory = isolated_session_factory(engine, schema)
    original_cursor = AutomaticTransfersCursor("62", "112")

    async def failing_run(
        received_session,
        *,
        reference_date,
        settings,
        max_teams,
        max_players,
        cursor,
    ):
        assert reference_date == DAY
        assert max_teams == 2
        assert max_players == 4
        assert cursor == original_cursor
        raise RuntimeError("simulated_ingestion_failure")

    monkeypatch.setattr(worker, "SessionFactory", factory)
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(worker, "run_sms24_automatic_transfers", failing_run)

    try:
        async with factory() as setup_session:
            async with setup_session.begin():
                repo = checkpoint_foundation.SMS24TransfersCheckpointRepository(
                    setup_session
                )
                await repo.start_run(
                    reference_date=DAY,
                    max_teams=2,
                    max_players=4,
                )
                await repo.save_progress(result(original_cursor))

        with pytest.raises(RuntimeError, match="simulated_ingestion_failure"):
            await worker._run_iteration(
                config(max_teams=99, max_players=99)
            )

        async with factory() as reader:
            async with reader.begin():
                checkpoint = (
                    await checkpoint_foundation.SMS24TransfersCheckpointRepository(
                        reader
                    ).get()
                )

        assert checkpoint.status == "running"
        assert checkpoint.reference_date == DAY
        assert checkpoint.max_teams == 2
        assert checkpoint.max_players == 4
        assert checkpoint.cursor == original_cursor
        assert checkpoint.completed_at is None
        assert checkpoint.failed_attempts == 0
    finally:
        await isolated_engine.dispose()


@pytest.mark.parametrize(
    ("state", "retry_after_seconds", "expected_delay"),
    [
        ("progress", None, 60),
        ("lock_busy", None, 17),
        ("waiting_cycle", 123.5, 123.5),
        ("completed", None, 21600),
        ("completed_with_errors", None, 21600),
    ],
)
async def test_run_worker_uses_delay_for_iteration_state(
    monkeypatch,
    state,
    retry_after_seconds,
    expected_delay,
):
    from app.sms24 import transfers_worker as worker

    worker_config = TransfersWorkerConfig(
        cycle_interval_seconds=21600,
        page_interval_seconds=60,
        retry_interval_seconds=300,
        lock_retry_seconds=17,
        max_teams=20,
        max_players=100,
    )
    sleeps = []

    async def fake_iteration(received_config):
        assert received_config == worker_config
        return worker.TransfersWorkerIteration(
            state=state,
            retry_after_seconds=retry_after_seconds,
        )

    async def fake_sleep(delay):
        sleeps.append(delay)
        raise asyncio.CancelledError

    monkeypatch.setattr(worker, "_env_bool", lambda *args, **kwargs: True)
    monkeypatch.setattr(worker, "_config_from_env", lambda: worker_config)
    monkeypatch.setattr(worker, "_run_iteration", fake_iteration)
    monkeypatch.setattr(worker.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await worker.run_worker()

    assert sleeps == [expected_delay]


async def test_run_worker_retries_after_error_without_logging_exception_message(
    monkeypatch,
    caplog,
):
    from app.sms24 import transfers_worker as worker

    worker_config = TransfersWorkerConfig(
        cycle_interval_seconds=21600,
        page_interval_seconds=60,
        retry_interval_seconds=300,
        lock_retry_seconds=17,
        max_teams=20,
        max_players=100,
    )
    sleeps = []
    secret_message = "SECRET_TOKEN_MUST_NOT_APPEAR"

    async def failing_iteration(received_config):
        assert received_config == worker_config
        raise RuntimeError(secret_message)

    async def fake_sleep(delay):
        sleeps.append(delay)
        raise asyncio.CancelledError

    monkeypatch.setattr(worker, "_env_bool", lambda *args, **kwargs: True)
    monkeypatch.setattr(worker, "_config_from_env", lambda: worker_config)
    monkeypatch.setattr(worker, "_run_iteration", failing_iteration)
    monkeypatch.setattr(worker.asyncio, "sleep", fake_sleep)

    with caplog.at_level("ERROR", logger="sms24.transfers_worker"):
        with pytest.raises(asyncio.CancelledError):
            await worker.run_worker()

    assert sleeps == [300]
    assert "RuntimeError" in caplog.text
    assert secret_message not in caplog.text


async def test_run_worker_propagates_cancellation_without_retry_or_sleep(
    monkeypatch,
):
    from app.sms24 import transfers_worker as worker

    worker_config = TransfersWorkerConfig(
        cycle_interval_seconds=21600,
        page_interval_seconds=60,
        retry_interval_seconds=300,
        lock_retry_seconds=17,
        max_teams=20,
        max_players=100,
    )
    sleeps = []

    async def cancelled_iteration(received_config):
        assert received_config == worker_config
        raise asyncio.CancelledError

    async def fake_sleep(delay):
        sleeps.append(delay)
        raise AssertionError("sleep must not be called after cancellation")

    monkeypatch.setattr(worker, "_env_bool", lambda *args, **kwargs: True)
    monkeypatch.setattr(worker, "_config_from_env", lambda: worker_config)
    monkeypatch.setattr(worker, "_run_iteration", cancelled_iteration)
    monkeypatch.setattr(worker.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await worker.run_worker()

    assert sleeps == []


async def test_disabled_worker_sleeps_without_running_ingestion(monkeypatch):
    from app.sms24 import transfers_worker as worker

    worker_config = TransfersWorkerConfig(
        cycle_interval_seconds=21600,
        page_interval_seconds=60,
        retry_interval_seconds=300,
        lock_retry_seconds=17,
        max_teams=20,
        max_players=100,
    )
    sleeps = []
    iteration_called = False

    async def forbidden_iteration(received_config):
        nonlocal iteration_called
        iteration_called = True
        raise AssertionError("disabled worker must not run ingestion")

    async def fake_sleep(delay):
        sleeps.append(delay)
        raise asyncio.CancelledError

    monkeypatch.setattr(worker, "_env_bool", lambda *args, **kwargs: False)
    monkeypatch.setattr(worker, "_config_from_env", lambda: worker_config)
    monkeypatch.setattr(worker, "_run_iteration", forbidden_iteration)
    monkeypatch.setattr(worker.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await worker.run_worker()

    assert iteration_called is False
    assert sleeps == [3600]
