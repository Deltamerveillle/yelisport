"""GNews integration in rollback-only schemas, all HTTP mocked."""

from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import delete, select

from app.models.sports_live import SportsDataSourceCapability
from app.sms24.providers.gnews import GNewsProvider
from tests import test_sms24_news_runner_postgres as runner_tests
from tests.test_sms24_gnews_provider import KEY, article, payload
from tests.test_sms24_news_contract import NOW
from tests.test_sms24_news_postgres import rows
from tests.test_sms24_news_registry import FakeNewsProvider

isolated_session = runner_tests.isolated_session
session = runner_tests.session


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", [200, 401, 403, 500, "json", "network"])
async def test_gnews_aggregation_health_neutral_and_safe(session, outcome, caplog):
    def handle(request):
        if outcome == "network":
            raise httpx.ConnectError(KEY, request=request)
        if outcome == 200:
            return httpx.Response(200, json=payload(article()))
        return httpx.Response(200 if outcome == "json" else outcome, text=KEY)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        gnews = GNewsProvider(api_key=KEY, client=client)
        other = FakeNewsProvider("other")
        service, sources = await runner_tests.setup(session, [gnews, other])
        for source in sources:
            source.health_status = "degraded"
            source.last_success_at = source.last_failure_at = source.last_checked_at = NOW
        await session.flush()
        await session.commit()  # Savepoint only: outer fixture transaction always rolls back.
        session.commit = AsyncMock(side_effect=AssertionError("Caller owns commit"))
        result = await service.run()
        expected = 2 if outcome == 200 else 1
        assert result.successes == expected and result.failures == 2 - expected
        assert other.fetch_calls == 1
        stored = await rows(session)
        assert len(stored) == expected
        assert {r.source_id for r in stored} == {
            s.id for s in (sources if outcome == 200 else sources[1:])
        }
        for source in sources:
            await session.refresh(source)
            assert (
                source.health_status,
                source.last_success_at,
                source.last_failure_at,
                source.last_checked_at,
            ) == ("degraded", NOW, NOW, NOW)
        if outcome in (401, 403):
            assert result.attempts[0].reason == "provider_access_restricted"
        assert KEY not in repr(result) + caplog.text
        await service.run()
        assert len(await rows(session)) == expected
        session.commit.assert_not_awaited()
        await session.rollback()
        assert await rows(session) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("ineligible", ["source_inactive", "capability_inactive", "no_capability"])
async def test_ineligible_gnews_never_called(session, ineligible):
    def unexpected(request):
        pytest.fail("Ineligible GNews must not be called")

    async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected)) as client:
        gnews = GNewsProvider(api_key=KEY, client=client)
        gnews.check_health = AsyncMock(wraps=gnews.check_health)
        service, sources = await runner_tests.setup(session, [gnews, FakeNewsProvider("other")])
        if ineligible == "source_inactive":
            sources[0].is_active = False
        elif ineligible == "no_capability":
            await session.execute(
                delete(SportsDataSourceCapability).where(
                    SportsDataSourceCapability.source_id == sources[0].id
                )
            )
        else:
            capability = await session.scalar(
                select(SportsDataSourceCapability).where(
                    SportsDataSourceCapability.source_id == sources[0].id
                )
            )
            capability.is_active = False
        await session.flush()
        result = await service.run()
        assert [a.provider_slug for a in result.attempts] == ["other"]
        gnews.check_health.assert_not_awaited()
