"""Independent News registry and empty runtime, without network access."""

import pytest

from app.core.config import Settings
from app.sms24.news_runtime import build_sms24_news_registry, build_sms24_news_runner
from app.sms24.providers.base import ProviderHealthResult
from app.sms24.providers.news import ProviderNewsResult
from app.sms24.providers.news_provider import NewsProvider
from app.sms24.providers.news_registry import NewsProviderRegistry
from tests.test_sms24_news_contract import NOW, article


class FakeNewsProvider(NewsProvider):
    def __init__(self, slug, *, error=None, health_error=None, healthy=True, empty=False):
        self.slug = self.name = slug
        self.error = error
        self.health_error = health_error
        self.healthy = healthy
        self.health_calls = self.fetch_calls = 0
        self.result = ProviderNewsResult(fetched_at=NOW, articles=() if empty else (article(),))

    async def check_health(self):
        self.health_calls += 1
        if self.health_error:
            raise self.health_error
        return ProviderHealthResult(is_healthy=self.healthy, checked_at=NOW)

    async def fetch_news(self):
        self.fetch_calls += 1
        if self.error:
            raise self.error
        return self.result


def test_registry_independent_contract_and_lifecycle():
    registry = NewsProviderRegistry()
    provider = FakeNewsProvider(" NEWS-A ")
    assert not hasattr(provider, "fetch_fixtures")
    registry.register(provider)
    assert registry.get(" news-A ") is provider
    assert registry.all() == [provider]
    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeNewsProvider("news-a"))
    registry.all().clear()
    assert registry.all() == [provider]
    registry.clear()
    assert registry.all() == []
    with pytest.raises(KeyError):
        registry.get("news-a")


@pytest.mark.parametrize("slug", ["", "  ", None])
def test_empty_slug_rejected(slug):
    with pytest.raises(ValueError):
        NewsProviderRegistry().register(FakeNewsProvider(slug))


def test_news_runtime_has_no_real_providers():
    settings = Settings(_env_file=None, sms24_gnews_api_key=None)
    assert build_sms24_news_registry(settings).all() == []
    assert build_sms24_news_runner(None, settings=settings).registry.all() == []
