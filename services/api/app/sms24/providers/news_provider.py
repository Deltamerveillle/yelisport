"""News-only provider interface, independent of fixture fetching."""

from abc import ABC, abstractmethod

from app.sms24.providers.base import ProviderHealthResult
from app.sms24.providers.news import ProviderNewsResult


class NewsProvider(ABC):
    slug: str
    name: str

    @abstractmethod
    async def fetch_news(self) -> ProviderNewsResult:
        """Fetch one provider-defined batch; no sport default or implicit entity mapping."""

    @abstractmethod
    async def check_health(self) -> ProviderHealthResult:
        """Check News availability; access restrictions use the shared safe exception."""
