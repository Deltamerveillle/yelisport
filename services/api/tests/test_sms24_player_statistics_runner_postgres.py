"""Real observation/savepoint behavior on opt-in disposable PostgreSQL schemas only."""

import re
import uuid
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import Base
from app.models.sport import Sport
from app.models.sports_live import SportsDataSource, SportsDataSourceCapability
from app.models.sports_player_statistics import SportsPlayerStatisticObservation as Observation
from app.sms24.player_statistics import SMS24PlayerStatisticsRepository
from app.sms24.player_statistics_runner import (
    PlayerStatisticsAllProvidersFailed,
    PlayerStatisticsRunner,
    PlayerStatisticsTarget,
)
from app.sms24.providers.base import ProviderHealthResult
from app.sms24.providers.player_statistics import (
    ProviderPlayerStatistic,
    ProviderPlayerStatisticsResult,
)
from app.sms24.providers.registry import ProviderRegistry
from tests import test_sms24_player_statistics_postgres as foundation

# Reuse existing isolated-schema fixtures, without importing/instantiating human models.
previous_connection = foundation.previous_connection
connection = foundation.connection
session = foundation.session
NOW = foundation.NOW


@pytest.fixture(autouse=True)
def no_http_or_resolution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("HTTP and automatic graph resolution are forbidden")

    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)
    monkeypatch.setattr(httpx.Client, "send", forbidden)
    monkeypatch.setattr(SMS24PlayerStatisticsRepository, "resolve_observation", forbidden)


def observation(external_id="record", **changes):
    return ProviderPlayerStatistic(
        **{
            "athlete_external_id": "758",
            "external_id": external_id,
            "scope": "season",
            "metrics": {"distance": None, "points": 0},
            "metadata": {"season_id": 825, "team_id": 62, "position_id": 25},
            **changes,
        },
    )


def result(*rows, fetched_at=NOW):
    return ProviderPlayerStatisticsResult(fetched_at=fetched_at, statistics=rows)


async def setup(session, slugs=("sportmonks",)):
    sport = Sport(slug="athletics", name="Athletics")
    session.add(sport)
    await session.flush()
    registry = ProviderRegistry()
    sources = {}
    for priority, slug in enumerate(slugs):
        source = SportsDataSource(
            slug=slug,
            name=slug,
            health_status="degraded",
            last_success_at=NOW,
            last_failure_at=NOW,
            last_checked_at=NOW,
        )
        session.add(source)
        await session.flush()
        sources[slug] = source.id
        session.add(
            SportsDataSourceCapability(
                source_id=source.id, capability="statistics", priority=priority
            )
        )
        registry.register(
            SimpleNamespace(
                slug=slug,
                check_health=AsyncMock(return_value=ProviderHealthResult(True, NOW)),
                fetch_player_statistics=AsyncMock(return_value=result(observation())),
            )
        )
    await session.flush()
    runner = PlayerStatisticsRunner(session=session, registry=registry)
    return runner, sources, {slug: PlayerStatisticsTarget("758", sport.id) for slug in slugs}


async def rows(session):
    return list(await session.scalars(select(Observation).order_by(Observation.source_id)))


PROTECTED = (
    "athlete_performances",
    "athletes",
    "users",
    "profiles",
    "sports_athlete_identity_links",
    "sports_competitors",
    "sports_canonical_competitors",
    "sports_canonical_transfers",
    "sports_fixtures",
    "sports_canonical_fixtures",
    "sports_seasons",
    "sports_data_sources",
    "sports_data_source_capabilities",
)


async def protected_snapshot(session):
    return {
        name: (await session.execute(select(Base.metadata.tables[name]))).mappings().all()
        for name in PROTECTED
    }


async def test_real_persistence_replay_stale_and_identity_boundaries(session):
    runner, sources, targets = await setup(session)
    before = await protected_snapshot(session)
    statements = []
    sync_connection = (await session.connection()).sync_connection

    def capture(conn, cursor, statement, params, context, executemany):
        statements.append(statement.lower())

    event.listen(sync_connection, "before_cursor_execute", capture)
    try:
        provider = runner.registry.get("sportmonks")
        provider.fetch_player_statistics.return_value = result(
            observation("one"), observation("two")
        )
        first = await runner.run(targets=targets)
        assert (first.successes, first.failures, first.observations_processed) == (1, 0, 2)
        original_ids = {row.id for row in await rows(session)}
        replay = await runner.run(targets=targets)
        assert replay.observations_processed == 2
        assert {row.id for row in await rows(session)} == original_ids
        provider.fetch_player_statistics.return_value = result(
            observation("one", metrics={"distance": 100}),
            fetched_at=NOW + timedelta(days=1),
        )
        await runner.run(targets=targets)
        provider.fetch_player_statistics.return_value = result(observation("one"))
        assert (await runner.run(targets=targets)).observations_processed == 1
        stored = await session.scalar(select(Observation).where(Observation.external_id == "one"))
        assert stored.metrics_json == {"distance": 100}
        # Equal timestamps may replace a snapshot with unknown values, never invented zeros.
        provider.fetch_player_statistics.return_value = result(
            observation("one"),
            fetched_at=NOW + timedelta(days=1),
        )
        await runner.run(targets=targets)
        stored_rows = await rows(session)
        assert all(row.source_id == sources["sportmonks"] for row in stored_rows)
        assert all(row.sport_id == targets["sportmonks"].sport_id for row in stored_rows)
        for row in stored_rows:
            assert row.metrics_json == {"distance": None, "points": 0}
            assert row.metadata_json == {"season_id": 825, "team_id": 62, "position_id": 25}
            assert (
                row.athlete_competitor_id
                is row.fixture_id
                is row.canonical_fixture_id
                is row.season_id
                is None
            )
        assert await protected_snapshot(session) == before
        # Also catch attempted UPDATE/DELETE even if protected tables contain zero rows.
        for statement in statements:
            if re.match(r"\s*(insert\s+into|update|delete\s+from)\b", statement):
                assert not any(re.search(r"\b" + name + r"\b", statement) for name in PROTECTED)
    finally:
        event.remove(sync_connection, "before_cursor_execute", capture)


@pytest.mark.parametrize("state", ["absent", "inactive", "source_inactive"])
async def test_capability_gates_network_and_never_activates(session, state):
    runner, _, targets = await setup(session)
    capability = await session.scalar(
        select(SportsDataSourceCapability).where(
            SportsDataSourceCapability.capability == "statistics",
        )
    )
    if state == "absent":
        await session.delete(capability)
    elif state == "inactive":
        capability.is_active = False
    else:
        source = await session.get(SportsDataSource, capability.source_id)
        source.is_active = False
    await session.flush()
    before = await protected_snapshot(session)
    with pytest.raises(PlayerStatisticsAllProvidersFailed) as caught:
        await runner.run(targets=targets)
    assert caught.value.attempts[0].reason == "statistics_capability_not_active"
    runner.registry.get("sportmonks").check_health.assert_not_awaited()
    assert await rows(session) == []
    assert await protected_snapshot(session) == before


@pytest.mark.parametrize("inactive", [False, True])
async def test_invalid_sport_blocks_entire_request_before_network(session, inactive):
    runner, _, targets = await setup(session, ("sportmonks", "other"))
    if inactive:
        sport = Sport(slug="inactive", name="Inactive", is_active=False)
        session.add(sport)
        await session.flush()
        identity = sport.id
    else:
        identity = uuid.uuid4()
    targets["other"] = replace(targets["other"], sport_id=identity)
    with pytest.raises(ValueError, match="exist and be active"):
        await runner.run(targets=targets)
    assert await rows(session) == []
    for provider in runner.registry.all():
        provider.check_health.assert_not_awaited()


async def test_same_provider_can_use_different_explicit_sports_without_competitor(session):
    runner, _, targets = await setup(session)
    first_sport = targets["sportmonks"].sport_id
    await runner.run(targets=targets)
    second_sport = Sport(slug="basketball", name="Basketball")
    session.add(second_sport)
    await session.flush()
    targets["sportmonks"] = replace(targets["sportmonks"], sport_id=second_sport.id)
    runner.registry.get("sportmonks").fetch_player_statistics.return_value = result(
        observation("second")
    )
    await runner.run(targets=targets)
    assert {row.sport_id for row in await rows(session)} == {first_sport, second_sport.id}
    assert (
        await session.scalar(
            select(func.count()).select_from(Base.metadata.tables["sports_competitors"])
        )
        == 0
    )


@pytest.mark.parametrize("bad_first", [False, True])
async def test_provider_batch_rollback_preserves_other_provider(session, bad_first):
    slugs = ("bad", "good") if bad_first else ("good", "bad")
    runner, sources, targets = await setup(session, slugs)
    await runner.ingestion_repository.record_observation(
        source_id=sources["bad"],
        sport_id=targets["bad"].sport_id,
        statistic=observation("conflict", athlete_external_id="different-player"),
        fetched_at=NOW,
    )
    runner.registry.get("bad").fetch_player_statistics.return_value = result(
        observation("would-be-rolled-back"),
        observation("conflict"),
    )
    output = await runner.run(targets=targets)
    assert (output.successes, output.failures, output.observations_processed) == (1, 1, 1)
    failed = next(attempt for attempt in output.attempts if not attempt.success)
    assert failed.reason == "ingestion_validation_failed"
    assert {(row.source_id, row.external_id) for row in await rows(session)} == {
        (sources["bad"], "conflict"),
        (sources["good"], "record"),
    }


async def test_multiple_successes_remain_separate_and_empty_is_success(session):
    runner, _, targets = await setup(session, ("one", "two"))
    output = await runner.run(targets=targets)
    assert output.successes == output.observations_processed == 2
    assert len({row.id for row in await rows(session)}) == 2
    for provider in runner.registry.all():
        provider.fetch_player_statistics.return_value = result()
    empty = await runner.run(targets=targets)
    assert empty.successes == 2 and empty.observations_processed == 0
    assert len(await rows(session)) == 2


async def test_real_sql_error_propagates_and_outer_transaction_remains_usable(session, monkeypatch):
    runner, _, targets = await setup(session)

    async def broken(**kwargs):
        await session.execute(text("SELECT * FROM missing_statistics_test_table"))

    monkeypatch.setattr(runner.ingestion_repository, "record_observation", broken)
    with pytest.raises(SQLAlchemyError):
        await runner.run(targets=targets)
    assert await rows(session) == []


async def test_caller_rollback_removes_successful_batch(session):
    runner, _, targets = await setup(session)
    with pytest.raises(RuntimeError, match="caller rollback"):
        async with session.begin_nested():
            await runner.run(targets=targets)
            assert len(await rows(session)) == 1
            raise RuntimeError("caller rollback")
    assert await rows(session) == []
