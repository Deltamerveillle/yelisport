import asyncio
from datetime import datetime, timezone
import signal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.sms24 import worker
from app.sms24.runner import SMS24AllProvidersFailed
from app.sms24.worker import (
    _env_positive_int,
    _utc_day_window,
)


def test_sms24_worker_builds_current_utc_day_window():
    starts_from, starts_until = _utc_day_window(
        datetime(
            2026,
            9,
            7,
            12,
            34,
            56,
            tzinfo=timezone.utc,
        )
    )

    assert starts_from == datetime(
        2026,
        9,
        7,
        0,
        0,
        0,
        tzinfo=timezone.utc,
    )

    assert starts_until.date().isoformat() == (
        "2026-09-07"
    )

    assert starts_until.tzinfo == timezone.utc


def test_sms24_worker_rejects_invalid_interval(
    monkeypatch,
):
    monkeypatch.setenv(
        "SMS24_LIVE_INTERVAL_SECONDS",
        "0",
    )

    with pytest.raises(
        ValueError,
        match="positive integer",
    ):
        _env_positive_int(
            "SMS24_LIVE_INTERVAL_SECONDS",
            3600,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, RuntimeError, SMS24AllProvidersFailed])
async def test_worker_default_cadence_and_failure_backoff(monkeypatch, caplog, failure):
    clock = SimpleNamespace(now=0)
    calls = []

    async def sleep(seconds):
        clock.now += seconds
        if clock.now >= 86400:
            raise asyncio.CancelledError

    async def ingest(*, live_only):
        calls.append((clock.now, live_only))
        if failure:
            raise failure("sensitive-provider-detail")

    monkeypatch.setenv("SMS24_WORKER_ENABLED", "true")
    for name in (
        "SMS24_FIXTURES_INTERVAL_SECONDS",
        "SMS24_LIVE_INTERVAL_SECONDS",
        "SMS24_WORKER_IDLE_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(sms24_api_football_key="test-key"))
    monkeypatch.setattr(worker, "_run_ingestion", ingest)
    monkeypatch.setattr(worker, "asyncio", SimpleNamespace(
        get_running_loop=lambda: SimpleNamespace(time=lambda: clock.now),
        sleep=sleep,
    ))

    with pytest.raises(asyncio.CancelledError):
        await worker.run_worker()

    assert [at for at, live in calls if not live] == [0, 21600, 43200, 64800]
    assert [at for at, live in calls if live] == list(range(3600, 86400, 3600))
    assert "sensitive-provider-detail" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled,key", [(False, "test-key"), (True, "")])
async def test_worker_does_not_ingest_when_disabled_or_key_missing(monkeypatch, enabled, key):
    monkeypatch.setenv("SMS24_WORKER_ENABLED", str(enabled))
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(sms24_api_football_key=key))
    ingest = AsyncMock()
    monkeypatch.setattr(worker, "_run_ingestion", ingest)
    monkeypatch.setattr(worker, "asyncio", SimpleNamespace(sleep=AsyncMock(side_effect=asyncio.CancelledError)))
    with pytest.raises(asyncio.CancelledError):
        await worker.run_worker()
    ingest.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
async def test_worker_signal_cancels_ingestion_and_disposes_engine(monkeypatch, signum):
    handlers = {}
    closed = []
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "add_signal_handler", lambda sig, callback: handlers.__setitem__(sig, callback))
    monkeypatch.setattr(loop, "remove_signal_handler", lambda sig: handlers.pop(sig))
    dispose = AsyncMock()
    monkeypatch.setattr(worker, "engine", SimpleNamespace(dispose=dispose))

    async def run():
        try:
            handlers[signum]()
            await asyncio.sleep(0)
        finally:
            closed.append(True)

    monkeypatch.setattr(worker, "run_worker", run)
    await asyncio.create_task(worker._serve())
    assert closed == [True]
    assert handlers == {}
    dispose.assert_awaited_once()
