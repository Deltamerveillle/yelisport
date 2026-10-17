"""Runner boundaries with stubbed persistence; no HTTP or human model imports."""

import ast
import inspect
import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.sms24 import player_statistics_runner as module
from app.sms24.player_statistics_runner import (
    PlayerStatisticsAllProvidersFailed,
    PlayerStatisticsRunner,
    PlayerStatisticsTarget,
)
from app.sms24.providers.base import ProviderHealthResult
from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.player_statistics import (
    ProviderPlayerStatistic,
    ProviderPlayerStatisticsResult,
)
from app.sms24.providers.registry import ProviderRegistry

NOW = datetime(2026, 9, 22, tzinfo=UTC)
SPORT = uuid.uuid4()
SOURCE = uuid.uuid4()
TARGET = PlayerStatisticsTarget("758", SPORT)
SECRET = "private-token-and-upstream-url"


def result(*items):
    return ProviderPlayerStatisticsResult(fetched_at=NOW, statistics=items)


def setup():
    session = MagicMock(spec=AsyncSession)
    session.scalars = AsyncMock(return_value=[SPORT])
    session.flush = AsyncMock()
    session.begin_nested.return_value = AsyncMock()
    provider = SimpleNamespace(
        slug="sportmonks",
        check_health=AsyncMock(return_value=ProviderHealthResult(True, NOW)),
        fetch_player_statistics=AsyncMock(return_value=result()),
    )
    registry = ProviderRegistry()
    registry.register(provider)
    runner = PlayerStatisticsRunner(session=session, registry=registry)
    runner.repository.list_active_sources_for_capability = AsyncMock(return_value=["sportmonks"])
    runner.repository.get_active_source_for_capability = AsyncMock(
        return_value=SimpleNamespace(id=SOURCE),
    )
    runner.ingestion_repository.record_observation = AsyncMock()
    return runner, provider


@pytest.mark.parametrize(
    "targets",
    [
        None,
        {},
        [],
        [("sportmonks", TARGET)],
        {"Sportmonks": TARGET},
        {" sportmonks": TARGET},
        {"sportmonks ": TARGET},
        {"": TARGET},
        {1: TARGET},
        {"sportmonks": "758"},
        {"sportmonks": None},
        {"sportmonks": {"athlete_external_id": "758", "sport_id": SPORT}},
        {"sportmonks": PlayerStatisticsTarget("758", str(SPORT))},
        {"sportmonks": PlayerStatisticsTarget("758", None)},
        {"sportmonks": PlayerStatisticsTarget(True, SPORT)},
        {"sportmonks": PlayerStatisticsTarget("", SPORT)},
        {"sportmonks": PlayerStatisticsTarget(" ", SPORT)},
        {"sportmonks": PlayerStatisticsTarget("x" * 161, SPORT)},
    ],
)
async def test_invalid_targets_before_io(targets):
    runner, provider = setup()
    with pytest.raises(ValueError):
        await runner.run(targets=targets)
    runner.session.scalars.assert_not_awaited()
    provider.check_health.assert_not_awaited()
    runner.ingestion_repository.record_observation.assert_not_awaited()


async def test_exact_target_type_and_immutable_fields():
    class OtherTarget(PlayerStatisticsTarget):
        pass

    runner, _ = setup()
    with pytest.raises(ValueError):
        await runner.run(targets={"sportmonks": OtherTarget("758", SPORT)})
    with pytest.raises(FrozenInstanceError):
        TARGET.sport_id = uuid.uuid4()


async def test_missing_active_sport_before_any_provider_call():
    runner, provider = setup()
    runner.session.scalars.return_value = []
    with pytest.raises(ValueError, match="exist and be active"):
        await runner.run(targets={"sportmonks": TARGET})
    provider.check_health.assert_not_awaited()
    runner.ingestion_repository.record_observation.assert_not_awaited()


@pytest.mark.parametrize(
    "state, reason",
    [
        ("inactive", "statistics_capability_not_active"),
        ("disappeared", "statistics_capability_not_active"),
        ("unregistered", "provider_not_registered"),
        ("unsupported", "statistics_not_supported"),
    ],
)
async def test_ineligible_provider_no_network(state, reason):
    runner, provider = setup()
    if state == "inactive":
        runner.repository.list_active_sources_for_capability.return_value = []
    elif state == "disappeared":
        runner.repository.get_active_source_for_capability.return_value = None
    elif state == "unregistered":
        runner.registry.clear()
    else:
        provider.fetch_player_statistics = None
    with pytest.raises(PlayerStatisticsAllProvidersFailed) as caught:
        await runner.run(targets={"sportmonks": TARGET})
    assert caught.value.attempts[0].reason == reason
    assert str(caught.value) == "No targeted SMS24 Player Statistics provider succeeded"
    provider.check_health.assert_not_awaited()
    runner.ingestion_repository.record_observation.assert_not_awaited()
    runner.repository.list_active_sources_for_capability.assert_awaited_once_with("statistics")


@pytest.mark.parametrize(
    "health",
    [
        None,
        True,
        ProviderHealthResult(False, NOW),
        ProviderHealthResult(1, NOW),
        RuntimeError(SECRET),
    ],
)
async def test_invalid_health_sanitized(health):
    runner, provider = setup()
    if isinstance(health, Exception):
        provider.check_health.side_effect = health
    else:
        provider.check_health.return_value = health
    with pytest.raises(PlayerStatisticsAllProvidersFailed) as caught:
        await runner.run(targets={"sportmonks": TARGET})
    assert caught.value.attempts[0].reason == "health_check_failed"
    assert SECRET not in repr(caught.value.attempts)
    provider.fetch_player_statistics.assert_not_awaited()


@pytest.mark.parametrize("stage", ["health", "fetch"])
async def test_access_restricted(stage):
    runner, provider = setup()
    call = provider.check_health if stage == "health" else provider.fetch_player_statistics
    call.side_effect = ProviderAccessRestrictedError()
    with pytest.raises(PlayerStatisticsAllProvidersFailed) as caught:
        await runner.run(targets={"sportmonks": TARGET})
    assert caught.value.attempts[0].reason == "provider_access_restricted"
    runner.ingestion_repository.record_observation.assert_not_awaited()


@pytest.mark.parametrize(
    "invalid",
    [
        "type",
        "none_time",
        "naive_time",
        "list",
        "bad_item",
        "bad_metrics",
        "other_player",
        "exception",
    ],
)
async def test_payload_revalidated_and_sanitized(invalid):
    runner, provider = setup()
    row = ProviderPlayerStatistic(athlete_external_id="758", external_id="record")
    payload = result(row)
    if invalid == "type":
        payload = {"statistics": ()}
    elif invalid in ("none_time", "naive_time"):
        object.__setattr__(
            payload, "fetched_at", None if invalid == "none_time" else NOW.replace(tzinfo=None)
        )
    elif invalid == "list":
        object.__setattr__(payload, "statistics", [row])
    elif invalid == "bad_item":
        object.__setattr__(payload, "statistics", (None,))
    elif invalid == "bad_metrics":
        row.metrics["nan"] = float("nan")
    elif invalid == "other_player":
        payload = result(ProviderPlayerStatistic(athlete_external_id="759", external_id="record"))
    else:
        provider.fetch_player_statistics.side_effect = RuntimeError(SECRET)
    provider.fetch_player_statistics.return_value = payload
    with pytest.raises(PlayerStatisticsAllProvidersFailed) as caught:
        await runner.run(targets={"sportmonks": TARGET})
    assert caught.value.attempts[0].reason == "fetch_or_payload_failed"
    assert SECRET not in repr(caught.value.attempts)
    runner.ingestion_repository.record_observation.assert_not_awaited()


@pytest.mark.parametrize("amount", [0, 1, 3])
async def test_success_exact_repository_arguments(amount):
    runner, provider = setup()
    rows = tuple(
        ProviderPlayerStatistic(athlete_external_id="758", external_id=str(i))
        for i in range(amount)
    )
    provider.fetch_player_statistics.return_value = result(*rows)
    output = await runner.run(targets={"sportmonks": TARGET})
    assert (output.successes, output.failures, output.observations_processed) == (1, 0, amount)
    provider.fetch_player_statistics.assert_awaited_once_with(athlete_external_id="758")
    assert runner.ingestion_repository.record_observation.await_count == amount
    for row in rows:
        runner.ingestion_repository.record_observation.assert_any_await(
            source_id=SOURCE,
            sport_id=SPORT,
            statistic=row,
            fetched_at=NOW,
        )
    runner.session.begin_nested.assert_called_once()
    runner.session.flush.assert_awaited_once()
    runner.session.commit.assert_not_called()
    runner.session.rollback.assert_not_called()


async def test_ingestion_value_error_is_sanitized():
    runner, provider = setup()
    provider.fetch_player_statistics.return_value = result(
        ProviderPlayerStatistic(athlete_external_id="758", external_id="r"),
    )
    runner.ingestion_repository.record_observation.side_effect = ValueError(SECRET)
    with pytest.raises(PlayerStatisticsAllProvidersFailed) as caught:
        await runner.run(targets={"sportmonks": TARGET})
    assert caught.value.attempts[0].reason == "ingestion_validation_failed"
    assert caught.value.attempts[0].observations_processed == 0


@pytest.mark.parametrize(
    "stage", ["sport", "sources", "source", "health", "fetch", "ingest", "flush"]
)
async def test_sql_errors_always_propagate(stage):
    runner, provider = setup()
    provider.fetch_player_statistics.return_value = result(
        ProviderPlayerStatistic(athlete_external_id="758", external_id="r"),
    )
    calls = {
        "sport": runner.session.scalars,
        "sources": runner.repository.list_active_sources_for_capability,
        "source": runner.repository.get_active_source_for_capability,
        "health": provider.check_health,
        "fetch": provider.fetch_player_statistics,
        "ingest": runner.ingestion_repository.record_observation,
        "flush": runner.session.flush,
    }
    error = SQLAlchemyError("database failure")
    calls[stage].side_effect = error
    with pytest.raises(SQLAlchemyError) as caught:
        await runner.run(targets={"sportmonks": TARGET})
    assert caught.value is error


async def test_unexpected_persistence_error_propagates():
    runner, _ = setup()
    runner.session.flush.side_effect = RuntimeError("unexpected persistence failure")
    with pytest.raises(RuntimeError, match="unexpected persistence"):
        await runner.run(targets={"sportmonks": TARGET})


def test_runner_has_no_human_domain_imports_or_writes():
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module.startswith("app.models"):
            assert node.module == "app.models.sport"
        if isinstance(node, ast.Attribute):
            assert node.attr not in {
                "resolve_observation",
                "link_athlete",
                "create_event",
                "commit",
                "rollback",
                "mark_failure",
                "mark_unavailable",
            }
