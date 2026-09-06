"""Tests for SMS24 runtime provider assembly."""

from unittest.mock import AsyncMock

from app.core.config import Settings
from app.sms24.providers.api_football import APIFootballProvider
from app.sms24.runtime import (
    build_sms24_provider_registry,
    build_sms24_runner,
)


def test_runtime_registry_skips_api_football_without_key():
    settings = Settings(
        sms24_api_football_key=None,
    )

    registry = build_sms24_provider_registry(settings)

    assert registry.all() == []


def test_runtime_registry_registers_api_football_with_key():
    settings = Settings(
        sms24_api_football_key="test-key",
    )

    registry = build_sms24_provider_registry(settings)

    providers = registry.all()

    assert len(providers) == 1
    assert isinstance(
        providers[0],
        APIFootballProvider,
    )
    assert providers[0].slug == "api-football"


def test_runtime_builds_runner():
    settings = Settings(
        sms24_api_football_key="test-key",
    )
    session = AsyncMock()

    runner = build_sms24_runner(
        session,
        settings=settings,
    )

    assert runner.registry.get(
        "api-football"
    ).slug == "api-football"

    assert runner.repository.session is session
    assert (
        runner.ingestion_service.repository.session
        is session
    )
