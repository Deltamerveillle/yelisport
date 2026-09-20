"""Durable Transfers traversal state. Caller owns the outer transaction.

Lock before reading state or running ingestion, and keep that transaction until
both observations and state have been saved. No worker or scheduling lives here.
"""

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sms24_job import SMS24JobCheckpoint
from app.sms24.transfers_batch import AutomaticTransfersCursor, AutomaticTransfersResult

SPORTMONKS_TRANSFERS_JOB = "sms24:sportmonks:transfers"


class CheckpointLockNotAcquired(RuntimeError):
    """Another transaction holds the job lock; retry later without ingestion."""


def checkpoint_lock_key(job_key: str) -> int:
    """Signed 64-bit SHA-256 prefix; stable across processes, unlike hash()."""
    if not isinstance(job_key, str) or not job_key.strip() or len(job_key) > 160:
        raise ValueError("Invalid SMS24 job key")
    digest = hashlib.sha256(("sms24-job-checkpoint:v1:" + job_key).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


@dataclass(frozen=True, slots=True)
class TransfersCheckpoint:
    job_key: str
    status: str
    reference_date: date | None
    cursor: AutomaticTransfersCursor | None
    max_teams: int | None
    max_players: int | None
    failed_attempts: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SMS24TransfersCheckpointRepository:
    """Typed Transfers API over the generic job table; never commits or rolls back.

    Every operation reacquires the same nonblocking transaction lock. This avoids
    trusting a stale Python 'locked' flag after commit, rollback or session reuse.
    Acquisition inside a savepoint is forbidden: its rollback could release locks.
    Direct SQL writers must observe the same cooperative advisory-lock protocol.
    """

    def __init__(self, session: AsyncSession, *, job_key: str = SPORTMONKS_TRANSFERS_JOB):
        self.session = session
        self.job_key = job_key
        self.lock_key = checkpoint_lock_key(job_key)

    async def try_acquire_lock(self) -> bool:
        if not self.session.in_transaction() or self.session.in_nested_transaction():
            raise RuntimeError("An outer transaction is required outside any savepoint")
        return bool(
            await self.session.scalar(
                text("SELECT pg_try_advisory_xact_lock(CAST(:key AS bigint))"),
                {"key": self.lock_key},
            )
        )

    async def _read(self) -> SMS24JobCheckpoint | None:
        if not await self.try_acquire_lock():
            raise CheckpointLockNotAcquired("checkpoint_lock_not_acquired")
        return await self.session.scalar(
            select(SMS24JobCheckpoint)
            .where(SMS24JobCheckpoint.job_key == self.job_key)
            .execution_options(populate_existing=True),
        )

    @staticmethod
    def _snapshot(row: SMS24JobCheckpoint) -> TransfersCheckpoint:
        return TransfersCheckpoint(
            job_key=row.job_key,
            status=row.status,
            reference_date=row.reference_date,
            cursor=AutomaticTransfersCursor(**row.cursor) if row.status == "running" else None,
            max_teams=row.parameters.get("max_teams"),
            max_players=row.parameters.get("max_players"),
            failed_attempts=row.failed_attempts,
            started_at=row.started_at,
            completed_at=row.completed_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get(self) -> TransfersCheckpoint | None:
        row = await self._read()
        return self._snapshot(row) if row is not None else None

    async def get_or_create(self) -> TransfersCheckpoint:
        row = await self._read()
        if row is None:
            row = SMS24JobCheckpoint(job_key=self.job_key)
            self.session.add(row)
            await self.session.flush()
        return self._snapshot(row)

    async def start_run(
        self,
        *,
        reference_date: date,
        max_teams: int = 20,
        max_players: int = 100,
    ) -> TransfersCheckpoint:
        if type(reference_date) is not date:
            raise ValueError("An explicit reference date is required")
        if any(type(n) is not int or not 1 <= n <= 2147483647 for n in (max_teams, max_players)):
            raise ValueError("Traversal limits must be positive integers")
        row = await self._read()
        if row is not None and row.status == "running":
            raise ValueError("A traversal is already running; resume its stored parameters")
        if row is None:
            row = SMS24JobCheckpoint(job_key=self.job_key)
            self.session.add(row)
        row.status = "running"
        row.reference_date = reference_date
        row.parameters = {"max_teams": max_teams, "max_players": max_players}
        row.cursor = asdict(AutomaticTransfersCursor())
        row.failed_attempts = 0
        row.started_at = datetime.now(UTC)
        row.completed_at = None
        row.updated_at = row.started_at
        await self.session.flush()
        return self._snapshot(row)

    async def _running(self) -> SMS24JobCheckpoint:
        row = await self._read()
        if row is None or row.status != "running":
            raise ValueError("No running traversal exists")
        return row

    @staticmethod
    def _failures(result: AutomaticTransfersResult) -> int:
        if not isinstance(result, AutomaticTransfersResult):
            raise ValueError("An automatic Transfers result is required")
        if result.discovery.reason is not None:
            raise ValueError("Discovery unavailable; retain checkpoint for retry")
        return sum(not attempt.success for attempt in result.discovery.attempts) + (
            result.batch.targets_failed
        )

    async def save_progress(self, result: AutomaticTransfersResult) -> TransfersCheckpoint:
        failures = self._failures(result)
        if not isinstance(result.next_cursor, AutomaticTransfersCursor):
            raise ValueError("No continuation; completion requires an explicit decision")
        row = await self._running()
        row.cursor = asdict(result.next_cursor)
        row.failed_attempts += failures
        row.updated_at = datetime.now(UTC)
        await self.session.flush()
        return self._snapshot(row)

    async def complete_run(self, result: AutomaticTransfersResult) -> TransfersCheckpoint:
        """Explicit caller decision to close a traversal, possibly with failures.

        Availability failures cannot complete it. Individual failures are retained
        across pages, so a clean final page cannot erase earlier errors.
        """
        failures = self._failures(result)
        if result.next_cursor is not None or result.discovery.has_more or result.batch.has_more:
            raise ValueError("Traversal still has a continuation")
        row = await self._running()
        row.failed_attempts += failures
        row.status = "completed_with_errors" if row.failed_attempts else "completed"
        row.cursor = {}
        row.completed_at = datetime.now(UTC)
        row.updated_at = row.completed_at
        await self.session.flush()
        return self._snapshot(row)
