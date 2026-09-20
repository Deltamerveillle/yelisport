"""Tests for SMS24 runtime provider assembly."""

from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.sms24.providers.api_football import APIFootballProvider
from app.sms24.runtime import (
    build_sms24_provider_registry,
    build_sms24_runner,
)


def test_runtime_registry_skips_api_football_without_key():
    settings = Settings(
        _env_file=None, sms24_sportmonks_key=None,
        sms24_api_football_key=None,
    )

    registry = build_sms24_provider_registry(settings)

    assert registry.all() == []


def test_runtime_registry_registers_api_football_with_key():
    settings = Settings(
        _env_file=None, sms24_sportmonks_key=None,
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
        _env_file=None, sms24_sportmonks_key=None,
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


@pytest.mark.parametrize("primary,secondary,slugs", [
    (None, None, []), ("", "  ", []),
    ("test-primary", None, ["api-football"]),
    (None, " test-secondary ", ["sportmonks"]),
    ("test-primary", "test-secondary", ["api-football", "sportmonks"]),
])
def test_runtime_independent_environment_keys(monkeypatch, primary, secondary, slugs):
    for variable, value in (("SMS24_API_FOOTBALL_KEY", primary),
                            ("SMS24_SPORTMONKS_KEY", secondary)):
        monkeypatch.delenv(variable, raising=False)
        if value is not None:
            monkeypatch.setenv(variable, value)
    settings = Settings(_env_file=None)
    registry = build_sms24_provider_registry(settings)
    assert [p.slug for p in registry.all()] == slugs


@pytest.mark.parametrize("key", [None, "test-token"])
def test_runtime_builds_transfers_without_activation_or_http(key, monkeypatch):
    import httpx

    from app.sms24.runtime import build_sms24_transfers_runner
    from app.sms24.transfers import SMS24TransfersRepository
    from app.sms24.transfers_runner import TransfersRunner

    monkeypatch.setattr(httpx.AsyncClient, "send", AsyncMock(
        side_effect=AssertionError("No HTTP during assembly")))
    settings = Settings(_env_file=None, sms24_api_football_key=key, sms24_sportmonks_key=key)
    session = AsyncMock()
    runner = build_sms24_transfers_runner(session, settings=settings)
    assert isinstance(runner, TransfersRunner)
    assert isinstance(runner.ingestion_repository, SMS24TransfersRepository)
    assert runner.session is runner.repository.session is session
    assert runner.ingestion_repository.session is session
    assert len(runner.registry.all()) == (2 if key else 0)
    assert all(not callable(getattr(p, "fetch_transfers", None)) for p in runner.registry.all())
    assert session.mock_calls == []
    httpx.AsyncClient.send.assert_not_called()
