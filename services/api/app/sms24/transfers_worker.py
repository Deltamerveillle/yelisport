"""Dedicated background worker for automatic SMS24 Transfers ingestion."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.db.session import SessionFactory, engine
from app.sms24.runtime import run_sms24_automatic_transfers
from app.sms24.transfers_batch import AutomaticTransfersCursor
from app.sms24.transfers_checkpoint import (
    SMS24TransfersCheckpointRepository,
)

logger = logging.getLogger("sms24.transfers_worker")

DEFAULT_CYCLE_INTERVAL_SECONDS = 6 * 60 * 60
DEFAULT_PAGE_INTERVAL_SECONDS = 60
DEFAULT_RETRY_INTERVAL_SECONDS = 5 * 60
DEFAULT_LOCK_RETRY_SECONDS = 60
DEFAULT_MAX_TEAMS = 20
DEFAULT_MAX_PLAYERS = 100


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        f"{name} must be a boolean: 1/0, true/false, yes/no, or on/off"
    )


def _env_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class TransfersWorkerConfig:
    cycle_interval_seconds: int
    page_interval_seconds: int
    retry_interval_seconds: int
    lock_retry_seconds: int
    max_teams: int
    max_players: int


@dataclass(frozen=True, slots=True)
class TransfersWorkerIteration:
    state: str
    observations_processed: int = 0
    targets_attempted: int = 0
    targets_failed: int = 0
    retry_after_seconds: float | None = None


def _config_from_env() -> TransfersWorkerConfig:
    return TransfersWorkerConfig(
        cycle_interval_seconds=_env_positive_int(
            "SMS24_TRANSFERS_CYCLE_INTERVAL_SECONDS",
            DEFAULT_CYCLE_INTERVAL_SECONDS,
        ),
        page_interval_seconds=_env_positive_int(
            "SMS24_TRANSFERS_PAGE_INTERVAL_SECONDS",
            DEFAULT_PAGE_INTERVAL_SECONDS,
        ),
        retry_interval_seconds=_env_positive_int(
            "SMS24_TRANSFERS_RETRY_INTERVAL_SECONDS",
            DEFAULT_RETRY_INTERVAL_SECONDS,
        ),
        lock_retry_seconds=_env_positive_int(
            "SMS24_TRANSFERS_LOCK_RETRY_SECONDS",
            DEFAULT_LOCK_RETRY_SECONDS,
        ),
        max_teams=_env_positive_int(
            "SMS24_TRANSFERS_MAX_TEAMS",
            DEFAULT_MAX_TEAMS,
        ),
        max_players=_env_positive_int(
            "SMS24_TRANSFERS_MAX_PLAYERS",
            DEFAULT_MAX_PLAYERS,
        ),
    )


async def _run_iteration(
    config: TransfersWorkerConfig,
) -> TransfersWorkerIteration:
    """Process exactly one bounded Transfers slice in one DB transaction."""
    settings = get_settings()

    async with SessionFactory() as session:
        async with session.begin():
            checkpoint_repo = SMS24TransfersCheckpointRepository(session)

            if not await checkpoint_repo.try_acquire_lock():
                logger.info("SMS24 Transfers worker lock occupied")
                return TransfersWorkerIteration(state="lock_busy")

            checkpoint = await checkpoint_repo.get_or_create()

            if checkpoint.status != "running":
                if checkpoint.completed_at is not None:
                    due_at = checkpoint.completed_at + timedelta(
                        seconds=config.cycle_interval_seconds
                    )
                    now = datetime.now(UTC)
                    if now < due_at:
                        return TransfersWorkerIteration(
                            state="waiting_cycle",
                            retry_after_seconds=max(
                                (due_at - now).total_seconds(),
                                0.0,
                            ),
                        )

                checkpoint = await checkpoint_repo.start_run(
                    reference_date=datetime.now(UTC).date(),
                    max_teams=config.max_teams,
                    max_players=config.max_players,
                )
                logger.info(
                    "SMS24 Transfers traversal started "
                    "reference_date=%s max_teams=%s max_players=%s",
                    checkpoint.reference_date,
                    checkpoint.max_teams,
                    checkpoint.max_players,
                )
            else:
                logger.info(
                    "SMS24 Transfers traversal resumed "
                    "reference_date=%s",
                    checkpoint.reference_date,
                )

            if (
                checkpoint.reference_date is None
                or checkpoint.max_teams is None
                or checkpoint.max_players is None
            ):
                raise RuntimeError("Invalid running Transfers checkpoint")

            cursor = checkpoint.cursor or AutomaticTransfersCursor()

            result = await run_sms24_automatic_transfers(
                session,
                reference_date=checkpoint.reference_date,
                settings=settings,
                max_teams=checkpoint.max_teams,
                max_players=checkpoint.max_players,
                cursor=cursor,
            )

            if result.discovery.reason is not None:
                raise RuntimeError("Transfers discovery unavailable")

            observations = result.batch.observations_processed
            attempted = result.batch.targets_attempted
            failed = result.batch.targets_failed

            if result.next_cursor is not None:
                await checkpoint_repo.save_progress(result)
                state = "progress"
                logger.info(
                    "SMS24 Transfers slice processed "
                    "targets=%s failed=%s observations=%s continuation=true",
                    attempted,
                    failed,
                    observations,
                )
            else:
                completed = await checkpoint_repo.complete_run(result)
                state = completed.status
                logger.info(
                    "SMS24 Transfers traversal finished "
                    "status=%s targets=%s failed=%s observations=%s",
                    completed.status,
                    attempted,
                    failed,
                    observations,
                )

            return TransfersWorkerIteration(
                state=state,
                observations_processed=observations,
                targets_attempted=attempted,
                targets_failed=failed,
            )


async def run_worker() -> None:
    enabled = _env_bool("SMS24_TRANSFERS_WORKER_ENABLED", False)
    config = _config_from_env()

    if not enabled:
        logger.warning(
            "SMS24 Transfers worker is disabled "
            "(SMS24_TRANSFERS_WORKER_ENABLED=false)"
        )
        while True:
            await asyncio.sleep(3600)

    logger.info(
        "SMS24 Transfers worker started "
        "cycle_interval=%ss page_interval=%ss "
        "retry_interval=%ss max_teams=%s max_players=%s",
        config.cycle_interval_seconds,
        config.page_interval_seconds,
        config.retry_interval_seconds,
        config.max_teams,
        config.max_players,
    )

    while True:
        delay = config.page_interval_seconds

        try:
            iteration = await _run_iteration(config)

            if iteration.state == "lock_busy":
                delay = config.lock_retry_seconds
            elif iteration.state == "waiting_cycle":
                if iteration.retry_after_seconds is None:
                    raise RuntimeError(
                        "waiting_cycle iteration requires retry_after_seconds"
                    )
                delay = iteration.retry_after_seconds
            elif iteration.state in {"completed", "completed_with_errors"}:
                delay = config.cycle_interval_seconds

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "SMS24 Transfers worker iteration failed (%s)",
                type(exc).__name__,
            )
            delay = config.retry_interval_seconds

        await asyncio.sleep(delay)


async def _serve() -> None:
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    assert task is not None

    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, task.cancel)

    try:
        await run_worker()
    except asyncio.CancelledError:
        logger.info("SMS24 Transfers worker stopped")
    finally:
        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(signum)
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
