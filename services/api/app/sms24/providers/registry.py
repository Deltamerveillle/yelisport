"""Registry for SMS24 sports-data providers."""

from __future__ import annotations

from app.sms24.providers.base import SportsDataProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, SportsDataProvider] = {}

    def register(self, provider: SportsDataProvider) -> None:
        slug = provider.slug.strip().lower()

        if not slug:
            raise ValueError("Provider slug must not be empty")

        if slug in self._providers:
            raise ValueError(
                f"Provider already registered: {slug}"
            )

        self._providers[slug] = provider

    def get(self, slug: str) -> SportsDataProvider:
        normalized = slug.strip().lower()

        try:
            return self._providers[normalized]
        except KeyError as exc:
            raise KeyError(
                f"Unknown SMS24 provider: {normalized}"
            ) from exc

    def all(self) -> list[SportsDataProvider]:
        return list(self._providers.values())

    def clear(self) -> None:
        self._providers.clear()
