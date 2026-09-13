"""News-only assembly. No real News adapter, credential or source is configured."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.sms24.news_runner import NewsRunner
from app.sms24.providers.news_registry import NewsProviderRegistry


def build_sms24_news_registry() -> NewsProviderRegistry:
    return NewsProviderRegistry()


def build_sms24_news_runner(session: AsyncSession) -> NewsRunner:
    return NewsRunner(session=session, registry=build_sms24_news_registry())
