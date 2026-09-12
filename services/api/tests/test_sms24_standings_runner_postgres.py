"""Standings fallback integration using mocked HTTP and disposable schemas."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.models.sport import Sport
from app.models.sports_live import SportsCanonicalCompetitor, SportsDataSource
from app.sms24.providers import ProviderRegistry, ProviderStandingsRequest
from app.sms24.providers.api_football import APIFootballProvider
from app.sms24.providers.sportmonks import SportmonksProvider
from app.sms24.runtime import build_sms24_standings_runner
from app.sms24.standings import SMS24StandingsRepository, StandingsIngestionService
from app.sms24.standings_runner import StandingsAllProvidersFailed, StandingsProviderRunner
from tests.test_sms24_standings_fetch import api_payload, sm_payload
from tests.test_sms24_standings_normalization import api_row
from tests.test_sms24_standings_postgres import observations, seed
from tests.test_sms24_standings_postgres import session as isolated_session

session = isolated_session
TARGETS = {
    "api-football": ProviderStandingsRequest(season="2026", league_external_id="7"),
    "sportmonks": ProviderStandingsRequest(season="88", league_external_id="7"),
}


def runner(session, client, service=None):
    registry = ProviderRegistry()
    registry.register(APIFootballProvider(api_key="test", client=client))
    registry.register(SportmonksProvider(api_key="test", client=client))
    return StandingsProviderRunner(
        session=session,
        registry=registry,
        ingestion_service=service or StandingsIngestionService(SMS24StandingsRepository(session)),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["http", "network", "health", "malformed"])
async def test_primary_failure_falls_back_with_provenance_and_no_duplicates(session, failure):
    _, sources, season = await seed(session)
    paths = []

    def handler(request):
        path = request.url.path
        paths.append(path)
        if path == "/status":
            return httpx.Response(503 if failure == "health" else 200, json={})
        if path == "/standings":
            if failure == "network":
                raise httpx.ConnectError("test failure", request=request)
            return httpx.Response(503 if failure == "http" else 200, json={"response": [{}]})
        if path.endswith("/standings/seasons/88"):
            return httpx.Response(200, json=sm_payload())
        return httpx.Response(200, json=sm_payload([]))  # Sportmonks health check.

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = runner(session, client)
        service.repository.mark_failure = AsyncMock(wraps=service.repository.mark_failure)
        for _ in range(2):
            result = await service.run(season_id=season.id, targets=TARGETS)
            assert result.provider_slug == "sportmonks"
            assert result.ingestion.rows_upserted == 1
            assert [attempt.success for attempt in result.attempts] == [False, True]
        assert service.repository.mark_failure.await_count == 2
    assert sources[0].last_failure_at is not None
    stored = await observations(session)
    assert len(stored) == 1
    assert stored[0].source_id == sources[1].id and stored[0].season_id == season.id
    assert stored[0].external_competitor_id == "42"
    assert sources[0].health_status == "degraded" and sources[1].health_status == "healthy"
    assert paths[0] == "/status"


@pytest.mark.asyncio
async def test_valid_empty_primary_succeeds_without_fallback_or_unhealthy_mark(session):
    _, sources, season = await seed(session)
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"response": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await runner(session, client).run(season_id=season.id, targets=TARGETS)
    assert result.provider_slug == "api-football" and result.ingestion.rows_upserted == 0
    assert paths == ["/status", "/standings"] and len(result.attempts) == 1
    assert sources[0].health_status == "healthy" and sources[0].last_failure_at is None
    assert await observations(session) == []


@pytest.mark.asyncio
async def test_caller_rollback_undoes_success_health_and_rows(session):
    sport, sources, season = await seed(session)
    await session.commit()
    sport_id, source_id, season_id = sport.id, sources[0].id, season.id
    sport.name = "Caller pending work"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=api_payload()))
    ) as client:
        result = await runner(session, client).run(season_id=season_id, targets=TARGETS)
    assert result.provider_slug == "api-football" and len(await observations(session)) == 1
    assert sport.name == "Caller pending work"
    await session.rollback()
    assert await observations(session) == []
    assert (await session.get(SportsDataSource, source_id)).last_success_at is None
    assert (await session.get(Sport, sport_id)).name == "Football"
    assert await session.scalar(select(func.count()).select_from(SportsCanonicalCompetitor)) == 0


@pytest.mark.asyncio
async def test_partial_primary_ingestion_is_rolled_back_before_fallback(session):
    sport, sources, season = await seed(session)
    sport.name = "Preserve caller changes"
    bad = api_row()
    bad["team"] = {"id": 999, "name": "---"}  # Invalid normalized canonical identity.

    def handler(request):
        if request.url.path == "/standings":
            return httpx.Response(200, json=api_payload([api_row(), bad]))
        if request.url.path.endswith("/standings/seasons/88"):
            return httpx.Response(200, json=sm_payload())
        return httpx.Response(200, json=sm_payload([]))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await runner(session, client).run(season_id=season.id, targets=TARGETS)
    assert result.attempts[0].reason == "ingestion_validation_failed"
    rows = await observations(session)
    assert len(rows) == 1 and rows[0].source_id == sources[1].id
    assert sport.name == "Preserve caller changes"
    assert await session.scalar(select(func.count()).select_from(SportsCanonicalCompetitor)) == 1


@pytest.mark.asyncio
async def test_database_failure_propagates_without_blame_or_fallback(session):
    _, sources, season = await seed(session)
    service = StandingsIngestionService(SMS24StandingsRepository(session))
    service.ingest_provider_result = AsyncMock(
        side_effect=IntegrityError("test", {}, Exception("database failure"))
    )
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json=api_payload())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(IntegrityError):
            await runner(session, client, service).run(season_id=season.id, targets=TARGETS)
    assert paths == ["/status", "/standings"]
    assert sources[0].health_status == "healthy"


@pytest.mark.asyncio
async def test_missing_configuration_all_failed_and_invalid_canonical_season(session):
    _, sources, season = await seed(session)
    service = StandingsProviderRunner(
        session=session,
        registry=ProviderRegistry(),
        ingestion_service=StandingsIngestionService(SMS24StandingsRepository(session)),
    )
    with pytest.raises(ValueError, match="existing canonical season"):
        await service.run(season_id=uuid.uuid4(), targets=TARGETS)
    with pytest.raises(StandingsAllProvidersFailed) as error:
        await service.run(season_id=season.id, targets=TARGETS)
    assert len(error.value.attempts) == 2
    assert all(attempt.reason == "provider_not_registered" for attempt in error.value.attempts)
    assert all(source.health_status == "unavailable" for source in sources)
    assert await observations(session) == []


def test_runtime_uses_existing_settings_and_provider_registry():
    service = build_sms24_standings_runner(
        None,
        settings=Settings(sms24_api_football_key="test", sms24_sportmonks_key="test"),
    )
    assert service.registry.get("api-football").slug == "api-football"
    assert service.registry.get("sportmonks").slug == "sportmonks"
    assert isinstance(service.ingestion_service, StandingsIngestionService)


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_health", ["healthy", "degraded"])
async def test_plan_restriction_falls_back_without_changing_source_health(session, initial_health):
    _, sources, season = await seed(session)
    primary = sources[0]
    previous = datetime(2026, 1, 1, tzinfo=UTC)
    primary.health_status = initial_health
    primary.last_failure_at = previous if initial_health == "degraded" else None
    primary.last_checked_at = previous
    primary.last_success_at = previous
    await session.flush()
    fields = ("health_status", "last_failure_at", "last_checked_at", "last_success_at")
    before = tuple(getattr(primary, field) for field in fields)

    def handler(request):
        if request.url.path == "/standings":
            return httpx.Response(200, json={"errors": {"plan": "private-secret restriction"}})
        if request.url.path.endswith("/standings/seasons/88"):
            return httpx.Response(200, json=sm_payload())
        return httpx.Response(200, json=sm_payload([]))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = runner(session, client)
        service.repository.mark_failure = AsyncMock(wraps=service.repository.mark_failure)
        service.repository.mark_unavailable = AsyncMock(wraps=service.repository.mark_unavailable)
        for _ in range(2):
            result = await service.run(season_id=season.id, targets=TARGETS)
            assert result.provider_slug == "sportmonks"
            assert result.ingestion.rows_upserted == 1
            assert [attempt.success for attempt in result.attempts] == [False, True]
            assert result.attempts[0].reason == "provider_access_restricted"
            assert "private-secret" not in repr(result.attempts)
        service.repository.mark_failure.assert_not_awaited()
        service.repository.mark_unavailable.assert_not_awaited()
    await session.refresh(primary)
    assert tuple(getattr(primary, field) for field in fields) == before
    stored = await observations(session)
    assert len(stored) == 1
    assert stored[0].source_id == sources[1].id
    assert stored[0].season_id == season.id
    assert stored[0].external_competitor_id == "42"
    assert sources[1].health_status == "healthy"
