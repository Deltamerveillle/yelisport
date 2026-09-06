"""Tests for the SMS24 provider abstraction."""

from datetime import datetime, timezone

import pytest

from app.sms24.providers import (
    ProviderFetchResult,
    ProviderFixture,
    ProviderHealthResult,
    ProviderRegistry,
    SportsDataProvider,
)


NOW = datetime(2026, 9, 6, 22, 0, tzinfo=timezone.utc)


class FakeProvider(SportsDataProvider):
    slug = "fake-provider"
    name = "Fake Provider"

    async def fetch_fixtures(
        self,
        *,
        sport_slug=None,
        starts_from=None,
        starts_until=None,
        live_only=False,
    ):
        return ProviderFetchResult(
            fixtures=[
                ProviderFixture(
                    external_id="fixture-1",
                    sport_slug=sport_slug or "football",
                    starts_at=NOW,
                    status="live" if live_only else "scheduled",
                )
            ],
            fetched_at=NOW,
            raw_count=1,
        )

    async def check_health(self):
        return ProviderHealthResult(
            is_healthy=True,
            checked_at=NOW,
            latency_ms=42,
        )


@pytest.mark.asyncio
async def test_provider_contract_fetches_normalized_fixture():
    provider = FakeProvider()

    result = await provider.fetch_fixtures(
        sport_slug="football",
        live_only=True,
    )

    assert result.raw_count == 1
    assert len(result.fixtures) == 1
    assert result.fixtures[0].external_id == "fixture-1"
    assert result.fixtures[0].sport_slug == "football"
    assert result.fixtures[0].status == "live"


@pytest.mark.asyncio
async def test_provider_contract_checks_health():
    provider = FakeProvider()

    health = await provider.check_health()

    assert health.is_healthy is True
    assert health.checked_at == NOW
    assert health.latency_ms == 42


def test_provider_registry_registers_and_resolves_provider():
    registry = ProviderRegistry()
    provider = FakeProvider()

    registry.register(provider)

    assert registry.get("fake-provider") is provider
    assert registry.get("FAKE-PROVIDER") is provider
    assert registry.all() == [provider]


def test_provider_registry_rejects_duplicates():
    registry = ProviderRegistry()
    registry.register(FakeProvider())

    with pytest.raises(ValueError):
        registry.register(FakeProvider())


def test_provider_registry_rejects_unknown_provider():
    registry = ProviderRegistry()

    with pytest.raises(KeyError):
        registry.get("missing")
