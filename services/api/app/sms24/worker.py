"""Background worker for continuous SMS24 sports ingestion."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from datetime import datetime, time, timezone

from app.core.config import get_settings
from app.db.session import SessionFactory, engine
from app.sms24.runner import SMS24AllProvidersFailed
from app.sms24.runtime import build_sms24_runner


logger = logging.getLogger("sms24.worker")

DEFAULT_FIXTURES_INTERVAL_SECONDS = 6 * 60 * 60
DEFAULT_LIVE_INTERVAL_SECONDS = 60 * 60
DEFAULT_IDLE_SLEEP_SECONDS = 30


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)

    if raw is None:
        return default

    return raw.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _env_positive_int(
    name: str,
    default: int,
) -> int:
    raw = os.getenv(name)

    if raw is None or not raw.strip():
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be a positive integer"
        ) from exc

    if value <= 0:
        raise ValueError(
            f"{name} must be a positive integer"
        )

    return value


def _utc_day_window(
    now: datetime,
) -> tuple[datetime, datetime]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError(
            "now must be timezone-aware"
        )

    current = now.astimezone(timezone.utc)

    starts_from = datetime.combine(
        current.date(),
        time.min,
        tzinfo=timezone.utc,
    )

    starts_until = datetime.combine(
        current.date(),
        time.max,
        tzinfo=timezone.utc,
    )

    return starts_from, starts_until


async def _run_ingestion(
    *,
    live_only: bool,
) -> None:
    async with SessionFactory() as session:
        runner = build_sms24_runner(session)

        if live_only:
            result = await runner.run(
                sport_slug="football",
                live_only=True,
            )
            mode = "live"
        else:
            starts_from, starts_until = (
                _utc_day_window(
                    datetime.now(timezone.utc)
                )
            )

            result = await runner.run(
                sport_slug="football",
                starts_from=starts_from,
                starts_until=starts_until,
                live_only=False,
            )
            mode = "fixtures"

        logger.info(
            "SMS24 ingestion succeeded "
            "mode=%s provider=%s fixtures=%s",
            mode,
            result.provider_slug,
            result.ingestion.fixtures_processed,
        )


async def run_worker() -> None:
    enabled = _env_bool(
        "SMS24_WORKER_ENABLED",
        False,
    )

    fixtures_interval = _env_positive_int(
        "SMS24_FIXTURES_INTERVAL_SECONDS",
        DEFAULT_FIXTURES_INTERVAL_SECONDS,
    )

    live_interval = _env_positive_int(
        "SMS24_LIVE_INTERVAL_SECONDS",
        DEFAULT_LIVE_INTERVAL_SECONDS,
    )

    idle_sleep = _env_positive_int(
        "SMS24_WORKER_IDLE_SECONDS",
        DEFAULT_IDLE_SLEEP_SECONDS,
    )

    settings = get_settings()

    if not enabled:
        logger.warning(
            "SMS24 worker is disabled "
            "(SMS24_WORKER_ENABLED=false)"
        )

        while True:
            await asyncio.sleep(3600)

    if not settings.sms24_api_football_key:
        logger.error(
            "SMS24 worker enabled but "
            "SMS24_API_FOOTBALL_KEY is missing"
        )

        while True:
            await asyncio.sleep(3600)

    logger.info(
        "SMS24 worker started "
        "fixtures_interval=%ss live_interval=%ss",
        fixtures_interval,
        live_interval,
    )

    loop = asyncio.get_running_loop()
    now_monotonic = loop.time()

    # Fetch today's global fixtures immediately.
    next_fixtures_at = now_monotonic

    # Do not immediately duplicate that request with live=all.
    next_live_at = now_monotonic + live_interval

    while True:
        now_monotonic = loop.time()

        if now_monotonic >= next_fixtures_at:
            # Move the deadline before the network request so a failure
            # cannot create a tight retry loop and consume provider quota.
            next_fixtures_at = (
                now_monotonic + fixtures_interval
            )

            try:
                await _run_ingestion(
                    live_only=False
                )
            except SMS24AllProvidersFailed:
                logger.error(
                    "SMS24 fixtures ingestion failed",
                )
            except Exception as exc:
                logger.error(
                    "Unexpected SMS24 fixtures "
                    "ingestion failure (%s)",
                    type(exc).__name__,
                )

        now_monotonic = loop.time()

        if now_monotonic >= next_live_at:
            next_live_at = (
                now_monotonic + live_interval
            )

            try:
                await _run_ingestion(
                    live_only=True
                )
            except SMS24AllProvidersFailed:
                logger.error(
                    "SMS24 live ingestion failed",
                )
            except Exception as exc:
                logger.error(
                    "Unexpected SMS24 live "
                    "ingestion failure (%s)",
                    type(exc).__name__,
                )

        await asyncio.sleep(idle_sleep)


async def _serve() -> None:
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    assert task is not None
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, task.cancel)
    try:
        await run_worker()
    except asyncio.CancelledError:
        logger.info("SMS24 worker stopped")
    finally:
        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(signum)
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
