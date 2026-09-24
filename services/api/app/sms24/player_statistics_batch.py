"""Batch orchestration for automatically discovered Player Statistics targets.

The existing single-target PlayerStatisticsRunner remains authoritative for
provider access, payload validation and observation persistence. This layer
only iterates provider-owned athlete targets and localizes expected runner
failures. It never resolves or writes human identity.
"""

from dataclasses import dataclass

from app.sms24.player_statistics_runner import (
    PlayerStatisticsAllProvidersFailed,
    PlayerStatisticsRunner,
)
from app.sms24.player_statistics_targets import (
    AutomaticPlayerStatisticsTarget,
    PlayerStatisticsTargetDiscoveryResult,
    as_runner_target,
)


@dataclass(frozen=True, slots=True)
class PlayerStatisticsTargetAttempt:
    provider_slug: str
    athlete_external_id: str
    success: bool
    reason: str | None = None
    observations_processed: int = 0


@dataclass(frozen=True, slots=True)
class PlayerStatisticsBatchResult:
    targets_discovered: int
    attempts: tuple[PlayerStatisticsTargetAttempt, ...]

    @property
    def targets_attempted(self) -> int:
        return len(self.attempts)

    @property
    def successes(self) -> int:
        return sum(attempt.success for attempt in self.attempts)

    @property
    def failures(self) -> int:
        return self.targets_attempted - self.successes

    @property
    def observations_processed(self) -> int:
        return sum(attempt.observations_processed for attempt in self.attempts)


@dataclass(frozen=True, slots=True)
class AutomaticPlayerStatisticsResult:
    discovery: PlayerStatisticsTargetDiscoveryResult
    batch: PlayerStatisticsBatchResult


class PlayerStatisticsBatchOrchestrator:
    """Run discovered provider athletes one by one through the frozen runner.

    Expected all-provider failures are local to the athlete. Unexpected errors,
    including SQLAlchemy errors propagated by the runner, remain fatal.
    Transaction ownership stays with the caller.
    """

    def __init__(self, *, runner: PlayerStatisticsRunner) -> None:
        if type(runner) is not PlayerStatisticsRunner:
            raise ValueError("PlayerStatisticsRunner required")
        self.runner = runner

    async def run(
        self,
        *,
        targets: tuple[AutomaticPlayerStatisticsTarget, ...],
    ) -> PlayerStatisticsBatchResult:
        if not isinstance(targets, tuple):
            raise ValueError("Supply Player Statistics targets as a tuple")

        attempts: list[PlayerStatisticsTargetAttempt] = []

        for target in targets:
            if type(target) is not AutomaticPlayerStatisticsTarget:
                raise ValueError("AutomaticPlayerStatisticsTarget required")

            try:
                result = await self.runner.run(
                    targets=as_runner_target(target),
                )
            except PlayerStatisticsAllProvidersFailed:
                attempts.append(
                    PlayerStatisticsTargetAttempt(
                        provider_slug=target.provider_slug,
                        athlete_external_id=target.athlete_external_id,
                        success=False,
                        reason="statistics_target_failed",
                    )
                )
                continue

            attempts.append(
                PlayerStatisticsTargetAttempt(
                    provider_slug=target.provider_slug,
                    athlete_external_id=target.athlete_external_id,
                    success=True,
                    observations_processed=result.observations_processed,
                )
            )

        return PlayerStatisticsBatchResult(
            targets_discovered=len(targets),
            attempts=tuple(attempts),
        )
