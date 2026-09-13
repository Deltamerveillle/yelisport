"""News-only assembly. Local registration never enables database capabilities."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.sms24.news_runner import NewsRunner
from app.sms24.providers.gnews import GNewsProvider
from app.sms24.providers.news_registry import NewsProviderRegistry


def build_sms24_news_registry(
    settings: Settings | None = None,
    *,
    query: str = "sport",
) -> NewsProviderRegistry:
    settings = settings or get_settings()
    registry = NewsProviderRegistry()
    key = settings.sms24_gnews_api_key
    if key is not None and key.get_secret_value().strip():
        registry.register(GNewsProvider(api_key=key.get_secret_value(), query=query))
    return registry


def build_sms24_news_runner(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
    query: str = "sport",
) -> NewsRunner:
    return NewsRunner(session=session, registry=build_sms24_news_registry(settings, query=query))
