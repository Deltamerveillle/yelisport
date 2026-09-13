"""News aggregation with fake providers and rollback-only PostgreSQL schemas."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.models.sports_live import SportsDataSource, SportsDataSourceCapability
from app.sms24.news_runner import NewsAllProvidersFailed, NewsRunner, NoActiveNewsSourcesError
from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.news import ProviderNewsResult
from app.sms24.providers.news_registry import NewsProviderRegistry
from tests import test_sms24_news_postgres as news_tests
from tests.test_sms24_news_contract import NOW, article
from tests.test_sms24_news_postgres import add, rows
from tests.test_sms24_news_registry import FakeNewsProvider

isolated_session = news_tests.session


@pytest.fixture
async def session(isolated_session):
    connection = await isolated_session.connection()
    await connection.run_sync(
        lambda conn: Base.metadata.create_all(conn, tables=[SportsDataSourceCapability.__table__])
    )
    yield isolated_session


async def setup(session, providers):
    registry = NewsProviderRegistry()
    sources = []
    for i, provider in enumerate(providers):
        source = await add(
            session,
            SportsDataSource,
            slug=provider.slug.strip().lower(),
            name=provider.name,
            priority=100 - i,
        )
        await add(
            session, SportsDataSourceCapability, source_id=source.id, capability="news", priority=i
        )
        registry.register(provider)
        sources.append(source)
    return NewsRunner(session=session, registry=registry, now_fn=lambda: NOW), sources


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_index", [None, 0, 1])
async def test_all_sources_processed_and_partial_success(session, failed_index):
    providers = [FakeNewsProvider("one"), FakeNewsProvider("two")]
    if failed_index is not None:
        providers[failed_index].error = RuntimeError("private-secret upstream body")
    service, sources = await setup(session, providers)
    result = await service.run()
    expected = 2 if failed_index is None else 1
    assert result.successes == expected and result.failures == 2 - expected
    assert result.ingestion.articles_upserted == expected
    assert [a.provider_slug for a in result.attempts] == ["one", "two"]
    assert all(p.fetch_calls == 1 for p in providers)
    assert "private-secret" not in repr(result)
    stored = await rows(session)
    assert {row.source_id for row in stored} == {
        source.id for i, source in enumerate(sources) if i != failed_index
    }
    assert len(stored) == expected
    if failed_index is not None:
        assert sources[failed_index].health_status == "healthy"
    await service.run()
    assert len(await rows(session)) == expected


@pytest.mark.asyncio
async def test_empty_valid_result_succeeds_and_does_not_stop_aggregation(session):
    providers = [FakeNewsProvider("empty", empty=True), FakeNewsProvider("other")]
    service, sources = await setup(session, providers)
    result = await service.run()
    assert result.successes == 2 and result.ingestion.articles_upserted == 1
    assert result.attempts[0].ingestion.articles_upserted == 0
    assert sources[0].health_status == "healthy" and sources[0].last_failure_at is None


@pytest.mark.asyncio
async def test_all_failures_have_safe_attempts(session):
    service, _ = await setup(
        session,
        [
            FakeNewsProvider("one", healthy=False),
            FakeNewsProvider("two", error=RuntimeError("private-secret")),
        ],
    )
    with pytest.raises(NewsAllProvidersFailed) as caught:
        await service.run()
    assert [a.reason for a in caught.value.attempts] == [
        "health_check_failed",
        "fetch_or_payload_failed",
    ]
    assert "private-secret" not in str(caught.value)


@pytest.mark.asyncio
async def test_no_active_news_sources(session):
    service = NewsRunner(session=session, registry=NewsProviderRegistry())
    with pytest.raises(NoActiveNewsSourcesError, match="No active SMS24 News") as caught:
        await service.run()
    assert caught.value.attempts == []


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["health", "fetch"])
async def test_access_restriction_preserves_shared_health(session, phase):
    restricted = FakeNewsProvider("restricted")
    if phase == "health":
        restricted.health_error = ProviderAccessRestrictedError()
    else:
        restricted.error = ProviderAccessRestrictedError()
    service, sources = await setup(session, [restricted, FakeNewsProvider("other")])
    sources[0].health_status = "degraded"
    sources[0].last_failure_at = NOW
    sources[0].last_checked_at = NOW
    await session.flush()
    service.repository.mark_failure = AsyncMock(wraps=service.repository.mark_failure)
    service.repository.mark_unavailable = AsyncMock(wraps=service.repository.mark_unavailable)
    result = await service.run()
    assert result.successes == 1
    assert result.attempts[0].reason == "provider_access_restricted"
    service.repository.mark_failure.assert_not_awaited()
    service.repository.mark_unavailable.assert_not_awaited()
    await session.refresh(sources[0])
    assert sources[0].health_status == "degraded"
    assert sources[0].last_failure_at == sources[0].last_checked_at == NOW
    assert sources[0].last_success_at is None


@pytest.mark.asyncio
async def test_missing_local_provider_does_not_change_health_or_stop_others(session):
    service, sources = await setup(
        session, [FakeNewsProvider("missing"), FakeNewsProvider("present")]
    )
    provider = service.registry.get("present")
    service.registry.clear()
    service.registry.register(provider)
    result = await service.run()
    assert result.attempts[0].reason == "provider_not_registered"
    assert result.successes == 1
    assert sources[0].health_status == "healthy" and sources[0].last_failure_at is None


@pytest.mark.asyncio
async def test_capability_selection_and_priority_with_no_ineligible_calls(session):
    registry = NewsProviderRegistry()
    providers = {}
    definitions = [
        ("z-first", "news", True, True, 1),
        ("b-tie", "news", True, True, 2),
        ("a-tie", "news", True, True, 2),
        ("disabled", "news", False, True, 0),
        ("cap-disabled", "news", True, False, 0),
        ("no-cap", None, True, True, 0),
    ]
    definitions += [(cap, cap, True, True, 0) for cap in ("fixtures", "live", "standings")]
    for slug, capability, active, enabled, priority in definitions:
        source = await add(
            session,
            SportsDataSource,
            slug=slug,
            name=slug,
            is_active=active,
            priority=100 - priority,
        )
        if capability:
            await add(
                session,
                SportsDataSourceCapability,
                source_id=source.id,
                capability=capability,
                is_active=enabled,
                priority=priority,
            )
        provider = FakeNewsProvider(slug, empty=True)
        providers[slug] = provider
        registry.register(provider)
    result = await NewsRunner(session=session, registry=registry).run()
    assert [a.provider_slug for a in result.attempts] == ["z-first", "a-tie", "b-tie"]
    for slug, provider in providers.items():
        expected = 1 if slug in ("z-first", "a-tie", "b-tie") else 0
        assert provider.health_calls == provider.fetch_calls == expected


@pytest.mark.asyncio
async def test_caller_transaction_owns_all_health_and_ingestion_writes(session):
    service, sources = await setup(session, [FakeNewsProvider("one"), FakeNewsProvider("two")])
    await session.commit()
    session.commit = AsyncMock(side_effect=AssertionError("No internal commit"))
    result = await service.run()
    assert result.successes == 2 and len(await rows(session)) == 2
    session.commit.assert_not_awaited()
    await session.rollback()
    assert await rows(session) == []
    for source in sources:
        await session.refresh(source)
        assert source.last_success_at is None


@pytest.mark.asyncio
async def test_invalid_ingestion_batch_rolls_back_and_other_source_succeeds(session):
    invalid = FakeNewsProvider("invalid")
    invalid.result = ProviderNewsResult(
        fetched_at=NOW,
        articles=(
            article(external_id="first"),
            article(external_id="second", publication_status="published"),
        ),
    )
    service, sources = await setup(session, [invalid, FakeNewsProvider("other")])
    result = await service.run()
    assert result.attempts[0].reason == "ingestion_validation_failed"
    assert {row.source_id for row in await rows(session)} == {sources[1].id}


@pytest.mark.asyncio
async def test_database_exception_propagates_without_provider_health_blame(session):
    service, sources = await setup(session, [FakeNewsProvider("one"), FakeNewsProvider("two")])
    service.ingestion_repository.ingest = AsyncMock(
        side_effect=IntegrityError("test", {}, Exception())
    )
    with pytest.raises(IntegrityError):
        await service.run()
    assert all(source.last_failure_at is None for source in sources)
    assert service.registry.get("two").fetch_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome,reason",
    [
        ("success", None),
        ("empty", None),
        ("health_failed", "health_check_failed"),
        ("health_exception", "health_check_failed"),
        ("fetch_failed", "fetch_or_payload_failed"),
        ("payload_invalid", "fetch_or_payload_failed"),
        ("ingestion_invalid", "ingestion_validation_failed"),
        ("restricted_health", "provider_access_restricted"),
        ("restricted_fetch", "provider_access_restricted"),
        ("missing", "provider_not_registered"),
    ],
)
@pytest.mark.parametrize("initial_status", ["healthy", "degraded", "unavailable"])
async def test_every_news_outcome_preserves_all_global_health_fields(
    session,
    outcome,
    reason,
    initial_status,
):
    provider = FakeNewsProvider("subject", empty=outcome == "empty")
    if outcome == "health_failed":
        provider.healthy = False
    elif outcome == "health_exception":
        provider.health_error = RuntimeError("health unavailable")
    elif outcome == "fetch_failed":
        provider.error = RuntimeError("fetch unavailable")
    elif outcome == "payload_invalid":
        provider.result = {"invalid": "payload"}
    elif outcome == "ingestion_invalid":
        provider.result = ProviderNewsResult(
            fetched_at=NOW,
            articles=(
                article(external_id="valid"),
                article(external_id="invalid", publication_status="published"),
            ),
        )
    elif outcome == "restricted_health":
        provider.health_error = ProviderAccessRestrictedError()
    elif outcome == "restricted_fetch":
        provider.error = ProviderAccessRestrictedError()
    service, sources = await setup(session, [provider, FakeNewsProvider("other")])
    if outcome == "missing":
        other = service.registry.get("other")
        service.registry.clear()
        service.registry.register(other)
    fields = ("health_status", "last_success_at", "last_failure_at", "last_checked_at")
    for source in sources:
        source.health_status = initial_status
        source.last_success_at = NOW - timedelta(days=3)
        source.last_failure_at = NOW - timedelta(days=2)
        source.last_checked_at = NOW - timedelta(days=1)
    await session.flush()
    before = [tuple(getattr(source, field) for field in fields) for source in sources]
    service.repository.mark_failure = AsyncMock(side_effect=AssertionError("No health writes"))
    service.repository.mark_unavailable = AsyncMock(side_effect=AssertionError("No health writes"))

    result = await service.run()

    assert result.attempts[0].reason == reason
    assert result.attempts[0].success == (reason is None)
    assert result.attempts[1].success  # Aggregation continues for every outcome.
    service.repository.mark_failure.assert_not_awaited()
    service.repository.mark_unavailable.assert_not_awaited()
    for source, expected in zip(sources, before, strict=True):
        await session.refresh(source)
        assert tuple(getattr(source, field) for field in fields) == expected
