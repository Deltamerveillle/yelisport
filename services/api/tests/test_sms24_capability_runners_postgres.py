"""Capability routing with isolated PostgreSQL schemas and fake/mocked providers."""

from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select

from app.models.sports_live import SportsDataSource, SportsDataSourceCapability
from app.sms24.providers import ProviderRegistry, ProviderStandingsRequest
from app.sms24.runner import SMS24AllProvidersFailed, SMS24ProviderRunner, SMS24RunnerRepository
from app.sms24.standings_runner import StandingsAllProvidersFailed
from tests.test_sms24_runner import NOW, FakeIngestionService, FakeProvider
from tests.test_sms24_standings_fetch import sm_payload
from tests.test_sms24_standings_postgres import session as isolated_session
from tests.test_sms24_standings_runner_postgres import TARGETS, runner, seed

session = isolated_session


async def source(session, slug, capability=None, *, active=True, enabled=True, priority=10):
    row = SportsDataSource(slug=slug, name=slug, priority=999, is_active=active)
    session.add(row)
    await session.flush()
    if capability:
        session.add(
            SportsDataSourceCapability(
                source_id=row.id, capability=capability, is_active=enabled, priority=priority
            )
        )
        await session.flush()
    return row


@pytest.mark.asyncio
@pytest.mark.parametrize("capability", ["fixtures", "live", "standings"])
async def test_repository_selects_only_active_capability_in_capability_priority_order(
    session, capability
):
    first = await source(session, "z-first", capability, priority=1)
    first.priority = 999
    await source(session, "b-tie", capability, priority=2)
    last = await source(session, "a-tie", capability, priority=2)
    last.priority = 0
    excluded = [
        await source(session, "news-only", "news"),
        await source(session, "source-disabled", capability, active=False),
        await source(session, "cap-disabled", capability, enabled=False),
        await source(session, "no-capability"),
    ]
    await session.flush()
    repo = SMS24RunnerRepository(session)
    assert await repo.list_active_sources_for_capability(capability) == [
        "z-first",
        "a-tie",
        "b-tie",
    ]
    assert (await repo.get_active_source_for_capability("z-first", capability)).id == first.id
    for slug in [*(row.slug for row in excluded), "unknown"]:
        assert await repo.get_active_source_for_capability(slug, capability) is None
    # Health lookup remains source-level, independent of capability.
    assert await repo.get_active_source("news-only") is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("live_only,expected", [(False, "fixtures-only"), (True, "live-only")])
async def test_fixture_runner_routes_without_probing_other_capabilities(
    session, live_only, expected
):
    registry = ProviderRegistry()
    providers = []
    for slug, capability in [
        ("fixtures-only", "fixtures"),
        ("live-only", "live"),
        ("news-only", "news"),
        ("no-capability", None),
    ]:
        await source(session, slug, capability)
        provider = FakeProvider(slug)
        provider.check_health = AsyncMock(wraps=provider.check_health)
        registry.register(provider)
        providers.append(provider)
    service = SMS24ProviderRunner(
        registry=registry,
        repository=SMS24RunnerRepository(session),
        ingestion_service=FakeIngestionService(),
        now_fn=lambda: NOW,
    )
    result = await service.run(live_only=live_only)
    assert result.provider_slug == expected
    for provider in providers:
        assert provider.fetch_calls == (1 if provider.slug == expected else 0)
        assert provider.check_health.await_count == (1 if provider.slug == expected else 0)


@pytest.mark.asyncio
async def test_no_capability_means_no_fixture_attempt(session):
    await source(session, "news-only", "news")
    service = SMS24ProviderRunner(
        registry=ProviderRegistry(),
        repository=SMS24RunnerRepository(session),
        ingestion_service=FakeIngestionService(),
        now_fn=lambda: NOW,
    )
    with pytest.raises(SMS24AllProvidersFailed, match="No active"):
        await service.run()


@pytest.mark.asyncio
async def test_standings_priority_comes_from_capability_not_target_order(session):
    _, sources, season = await seed(session)
    capability = await session.scalar(
        select(SportsDataSourceCapability).where(
            SportsDataSourceCapability.source_id == sources[1].id
        )
    )
    capability.priority = 0
    paths = []

    def handler(request):
        paths.append(request.url.path)
        assert request.url.path != "/status"
        return httpx.Response(
            200,
            json=sm_payload()
            if request.url.path.endswith("/standings/seasons/88")
            else sm_payload([]),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await runner(session, client).run(season_id=season.id, targets=TARGETS)
    assert result.provider_slug == "sportmonks" and result.ingestion.rows_upserted == 1
    assert len(result.attempts) == 1
    assert "/standings" not in paths


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason",
    ["inactive_capability", "inactive_source", "news_only", "missing_capability", "unknown"],
)
async def test_explicit_standings_target_without_active_capability_is_not_probed(session, reason):
    _, sources, season = await seed(session)
    capability = await session.scalar(
        select(SportsDataSourceCapability).where(
            SportsDataSourceCapability.source_id == sources[0].id
        )
    )
    slug = "api-football"
    if reason == "inactive_capability":
        capability.is_active = False
    elif reason == "inactive_source":
        sources[0].is_active = False
    elif reason == "news_only":
        capability.capability = "news"
    elif reason == "missing_capability":
        await session.delete(capability)
    else:
        slug = "unknown"
    await session.flush()
    before = (sources[0].health_status, sources[0].last_failure_at)
    targets = {
        slug: ProviderStandingsRequest(season="2026", league_external_id="7"),
        "sportmonks": TARGETS["sportmonks"],
    }

    def handler(request):
        assert request.url.path != "/status"
        return httpx.Response(
            200,
            json=sm_payload()
            if request.url.path.endswith("/standings/seasons/88")
            else sm_payload([]),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = runner(session, client)
        service.repository.mark_failure = AsyncMock(wraps=service.repository.mark_failure)
        service.repository.mark_unavailable = AsyncMock(wraps=service.repository.mark_unavailable)
        result = await service.run(season_id=season.id, targets=targets)
        assert result.provider_slug == "sportmonks"
        assert result.attempts[0].provider_slug == slug
        assert result.attempts[0].reason == "standings_capability_not_active"
        assert not result.attempts[0].success
        service.repository.mark_failure.assert_not_awaited()
        service.repository.mark_unavailable.assert_not_awaited()
    assert (sources[0].health_status, sources[0].last_failure_at) == before


@pytest.mark.asyncio
async def test_only_ineligible_explicit_target_fails_without_trying_untargeted_source(session):
    _, _, season = await seed(session)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("No HTTP expected"))
    ) as client:
        with pytest.raises(StandingsAllProvidersFailed) as caught:
            await runner(session, client).run(
                season_id=season.id, targets={"unknown": ProviderStandingsRequest(season="2026")}
            )
    assert [a.reason for a in caught.value.attempts] == ["standings_capability_not_active"]
