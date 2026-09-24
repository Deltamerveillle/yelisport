import uuid
from unittest.mock import AsyncMock

import pytest

from app.sms24.player_statistics_batch import PlayerStatisticsBatchOrchestrator
from app.sms24.player_statistics_runner import (
    PlayerStatisticsAllProvidersFailed,
    PlayerStatisticsProviderAttempt,
    PlayerStatisticsRunner,
    PlayerStatisticsRunnerResult,
    PlayerStatisticsTarget,
)
from app.sms24.player_statistics_targets import AutomaticPlayerStatisticsTarget

SPORT = uuid.uuid4()


def target(player_id: str) -> AutomaticPlayerStatisticsTarget:
    return AutomaticPlayerStatisticsTarget(
        provider_slug="sportmonks",
        athlete_external_id=player_id,
        sport_id=SPORT,
    )


def orchestrator():
    runner = object.__new__(PlayerStatisticsRunner)
    runner.run = AsyncMock()
    return runner, PlayerStatisticsBatchOrchestrator(runner=runner)


@pytest.mark.asyncio
async def test_runs_each_target_through_existing_runner():
    runner, batch = orchestrator()
    runner.run.side_effect = [
        PlayerStatisticsRunnerResult(
            [PlayerStatisticsProviderAttempt("sportmonks", True, observations_processed=3)]
        ),
        PlayerStatisticsRunnerResult(
            [PlayerStatisticsProviderAttempt("sportmonks", True, observations_processed=5)]
        ),
    ]

    result = await batch.run(targets=(target("758"), target("759")))

    assert result.targets_discovered == 2
    assert result.targets_attempted == 2
    assert result.successes == 2
    assert result.failures == 0
    assert result.observations_processed == 8
    assert runner.run.await_args_list[0].kwargs["targets"] == {
        "sportmonks": PlayerStatisticsTarget("758", SPORT)
    }
    assert runner.run.await_args_list[1].kwargs["targets"] == {
        "sportmonks": PlayerStatisticsTarget("759", SPORT)
    }


@pytest.mark.asyncio
async def test_expected_runner_failure_is_local_and_next_target_continues():
    runner, batch = orchestrator()
    runner.run.side_effect = [
        PlayerStatisticsAllProvidersFailed(
            [PlayerStatisticsProviderAttempt("sportmonks", False, "private-upstream-detail")]
        ),
        PlayerStatisticsRunnerResult(
            [PlayerStatisticsProviderAttempt("sportmonks", True, observations_processed=2)]
        ),
    ]

    result = await batch.run(targets=(target("758"), target("759")))

    assert result.successes == 1
    assert result.failures == 1
    assert result.attempts[0].reason == "statistics_target_failed"
    assert "private-upstream-detail" not in repr(result)
    assert result.attempts[1].success is True
    assert runner.run.await_count == 2


@pytest.mark.asyncio
async def test_unexpected_runner_error_propagates():
    runner, batch = orchestrator()
    runner.run.side_effect = RuntimeError("unexpected")

    with pytest.raises(RuntimeError, match="unexpected"):
        await batch.run(targets=(target("758"),))


@pytest.mark.asyncio
async def test_empty_tuple_is_valid_empty_batch():
    runner, batch = orchestrator()

    result = await batch.run(targets=())

    assert result.targets_discovered == 0
    assert result.targets_attempted == 0
    assert result.observations_processed == 0
    runner.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejects_non_tuple_and_non_exact_target():
    _, batch = orchestrator()

    with pytest.raises(ValueError):
        await batch.run(targets=[target("758")])

    with pytest.raises(ValueError):
        await batch.run(targets=(object(),))


def test_requires_exact_runner():
    with pytest.raises(ValueError):
        PlayerStatisticsBatchOrchestrator(runner=object())
