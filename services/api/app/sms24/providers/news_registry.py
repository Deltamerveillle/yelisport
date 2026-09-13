"""Independent registry of News-only adapters."""

from app.sms24.providers.news_provider import NewsProvider


class NewsProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, NewsProvider] = {}

    @staticmethod
    def _slug(slug: str) -> str:
        if not isinstance(slug, str) or not slug.strip():
            raise ValueError("News provider slug must not be empty")
        return slug.strip().lower()

    def register(self, provider: NewsProvider) -> None:
        slug = self._slug(provider.slug)
        if slug in self._providers:
            raise ValueError("News provider already registered")
        self._providers[slug] = provider

    def get(self, slug: str) -> NewsProvider:
        try:
            return self._providers[self._slug(slug)]
        except KeyError:
            raise KeyError("Unknown News provider") from None

    def all(self) -> list[NewsProvider]:
        return list(self._providers.values())

    def clear(self) -> None:
        self._providers.clear()
