"""Tests for SMS24 resilient provider orchestration."""

from datetime import datetime, timedelta, timezone

import pytest

from app.sms24.ingestion import SMS24IngestionStats
from app.sms24.providers import (
    ProviderFetchResult,
    ProviderHealthResult,
    ProviderRegistry,
    SportsDataProvider,
)
from app.sms24.runner import (
    SMS24AllProvidersFailed,
    SMS24ProviderRunner,
)


NOW = datetime(
    2026,
    9,
    6,
    23,
    0,
    tzinfo=timezone.utc,
)


class FakeProvider(SportsDataProvider):
    def __init__(
        self,
        slug,
        *,
        healthy=True,
        health_error=False,
        fetch_error=False,
        fetched_at=NOW,
    ):
        self.slug = slug
        self.name = slug
        self.healthy = healthy
        self.health_error = health_error
        self.fetch_error = fetch_error
        self.fetched_at = fetched_at
        self.fetch_calls = 0

    async def check_health(self):
        if self.health_error:
            raise RuntimeError("health unavailable")

        return ProviderHealthResult(
            is_healthy=self.healthy,
            checked_at=NOW,
        )

    async def fetch_fixtures(
        self,
        *,
        sport_slug=None,
        starts_from=None,
        starts_until=None,
        live_only=False,
    ):
        self.fetch_calls += 1

        if self.fetch_error:
            raise RuntimeError("provider fetch failed")

        return ProviderFetchResult(
            fixtures=[],
            fetched_at=self.fetched_at,
            raw_count=0,
        )


class FakeRepository:
    def __init__(self, slugs):
        self.sources = list(slugs)
        self.failures = []
        self.unavailable = []
        self.commits = 0
        self.rollbacks = 0

    async def list_active_sources(self):
        return self.sources

    async def mark_failure(
        self,
        slug,
        *,
        checked_at,
    ):
        self.failures.append(slug)

    async def mark_unavailable(
        self,
        slug,
        *,
        checked_at,
    ):
        self.unavailable.append(slug)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class FakeIngestionService:
    def __init__(self, failing=None):
        self.failing = set(failing or [])
        self.calls = []

    async def ingest_provider_result(
        self,
        *,
        provider,
        result,
    ):
        self.calls.append(provider.slug)

        if provider.slug in self.failing:
            raise RuntimeError("ingestion failed")

        return SMS24IngestionStats(
            provider_slug=provider.slug,
            fixtures_processed=len(result.fixtures),
            fetched_at=result.fetched_at,
        )


def make_runner(
    slugs,
    providers,
    *,
    failing_ingestion=None,
):
    registry = ProviderRegistry()

    for provider in providers:
        registry.register(provider)

    repository = FakeRepository(slugs)
    ingestion = FakeIngestionService(
        failing=failing_ingestion
    )

    runner = SMS24ProviderRunner(
        registry=registry,
        repository=repository,
        ingestion_service=ingestion,
        max_result_age=timedelta(minutes=10),
        now_fn=lambda: NOW,
    )

    return runner, repository, ingestion


@pytest.mark.asyncio
async def test_runner_uses_first_healthy_provider():
    primary = FakeProvider("primary")
    secondary = FakeProvider("secondary")

    runner, repository, ingestion = make_runner(
        ["primary", "secondary"],
        [primary, secondary],
    )

    result = await runner.run(live_only=True)

    assert result.provider_slug == "primary"
    assert ingestion.calls == ["primary"]
    assert primary.fetch_calls == 1
    assert secondary.fetch_calls == 0
    assert repository.failures == []


@pytest.mark.asyncio
async def test_runner_fails_over_from_unhealthy_provider():
    primary = FakeProvider(
        "primary",
        healthy=False,
    )
    secondary = FakeProvider("secondary")

    runner, repository, ingestion = make_runner(
        ["primary", "secondary"],
        [primary, secondary],
    )

    result = await runner.run()

    assert result.provider_slug == "secondary"
    assert repository.failures == ["primary"]
    assert ingestion.calls == ["secondary"]

    assert [
        attempt.reason
        for attempt in result.attempts
    ] == [
        "provider_unhealthy",
        None,
    ]


@pytest.mark.asyncio
async def test_runner_fails_over_after_fetch_failure():
    primary = FakeProvider(
        "primary",
        fetch_error=True,
    )
    secondary = FakeProvider("secondary")

    runner, repository, ingestion = make_runner(
        ["primary", "secondary"],
        [primary, secondary],
    )

    result = await runner.run()

    assert result.provider_slug == "secondary"
    assert repository.failures == ["primary"]
    assert ingestion.calls == ["secondary"]


@pytest.mark.asyncio
async def test_runner_rejects_stale_result_and_fails_over():
    primary = FakeProvider(
        "primary",
        fetched_at=NOW - timedelta(minutes=30),
    )
    secondary = FakeProvider("secondary")

    runner, repository, ingestion = make_runner(
        ["primary", "secondary"],
        [primary, secondary],
    )

    result = await runner.run()

    assert result.provider_slug == "secondary"
    assert repository.failures == ["primary"]
    assert ingestion.calls == ["secondary"]

    assert result.attempts[0].reason == (
        "stale_provider_result"
    )


@pytest.mark.asyncio
async def test_runner_marks_missing_provider_unavailable():
    secondary = FakeProvider("secondary")

    runner, repository, ingestion = make_runner(
        ["missing-provider", "secondary"],
        [secondary],
    )

    result = await runner.run()

    assert result.provider_slug == "secondary"
    assert repository.unavailable == [
        "missing-provider"
    ]
    assert ingestion.calls == ["secondary"]


@pytest.mark.asyncio
async def test_runner_fails_over_after_ingestion_failure():
    primary = FakeProvider("primary")
    secondary = FakeProvider("secondary")

    runner, repository, ingestion = make_runner(
        ["primary", "secondary"],
        [primary, secondary],
        failing_ingestion={"primary"},
    )

    result = await runner.run()

    assert result.provider_slug == "secondary"
    assert repository.failures == ["primary"]
    assert ingestion.calls == [
        "primary",
        "secondary",
    ]


@pytest.mark.asyncio
async def test_runner_raises_when_all_providers_fail():
    primary = FakeProvider(
        "primary",
        healthy=False,
    )
    secondary = FakeProvider(
        "secondary",
        fetch_error=True,
    )

    runner, repository, ingestion = make_runner(
        ["primary", "secondary"],
        [primary, secondary],
    )

    with pytest.raises(
        SMS24AllProvidersFailed,
        match="All SMS24 providers failed",
    ):
        await runner.run()

    assert repository.failures == [
        "primary",
        "secondary",
    ]
    assert ingestion.calls == []


@pytest.mark.asyncio
async def test_runner_rejects_naive_freshness_timestamp():
    primary = FakeProvider(
        "primary",
        fetched_at=datetime(
            2026,
            9,
            6,
            23,
            0,
        ),
    )

    runner, repository, ingestion = make_runner(
        ["primary"],
        [primary],
    )

    with pytest.raises(SMS24AllProvidersFailed):
        await runner.run()

    assert repository.failures == ["primary"]
    assert ingestion.calls == []
