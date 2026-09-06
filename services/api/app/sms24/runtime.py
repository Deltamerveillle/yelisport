"""Runtime assembly for SMS24 provider ingestion."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.sms24.ingestion import (
    SMS24IngestionRepository,
    SMS24IngestionService,
)
from app.sms24.providers.api_football import APIFootballProvider
from app.sms24.providers.registry import ProviderRegistry
from app.sms24.runner import (
    SMS24ProviderRunner,
    SMS24RunnerRepository,
)


def build_sms24_provider_registry(
    settings: Settings | None = None,
) -> ProviderRegistry:
    """Build the provider registry from runtime configuration."""

    settings = settings or get_settings()
    registry = ProviderRegistry()

    api_football_key = settings.sms24_api_football_key

    if api_football_key and api_football_key.strip():
        registry.register(
            APIFootballProvider(
                api_key=api_football_key,
            )
        )

    return registry


def build_sms24_runner(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
) -> SMS24ProviderRunner:
    """Assemble the SMS24 runner around one database session."""

    registry = build_sms24_provider_registry(settings)

    ingestion_repository = SMS24IngestionRepository(
        session
    )
    ingestion_service = SMS24IngestionService(
        ingestion_repository
    )

    runner_repository = SMS24RunnerRepository(
        session
    )

    return SMS24ProviderRunner(
        registry=registry,
        repository=runner_repository,
        ingestion_service=ingestion_service,
    )
