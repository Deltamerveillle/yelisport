"""Strict identity contract and Sportmonks HTTP adapter, with no real network."""

from datetime import UTC, datetime

import httpx
import pytest

from app.sms24.providers.player_identity import ProviderPlayerIdentity
from app.sms24.providers.sportmonks import SportmonksProvider


async def fetch(payload, player="758", status=200):
    def handler(request):
        assert request.url.path == "/v3/football/players/758"
        assert not request.url.params
        assert request.headers["Authorization"] == "secret-test-token"
        return httpx.Response(status, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await SportmonksProvider(
            api_key="secret-test-token", client=client
        ).fetch_player_identity(
            athlete_external_id=player,
        )


async def test_official_identity_without_statistics_or_optional_guesses():
    result = await fetch({"data": {"id": 758, "name": "James Tavernier", "country_id": 5}})
    assert result.external_id == "758"
    assert result.name == "James Tavernier"
    assert result.fetched_at.utcoffset().total_seconds() == 0
    assert not hasattr(result, "country_code")


@pytest.mark.parametrize("name", [None, "", " ", 12, True, [], {}, "bad\x00name", "a" * 201])
async def test_invalid_name(name):
    with pytest.raises(ValueError):
        await fetch({"data": {"id": 758, "name": name}})


@pytest.mark.parametrize(
    "identity", [None, False, True, 0, -1, 1.5, " 758", "٧٥٨", "0", "9" * 161, 759]
)
async def test_invalid_returned_id(identity):
    with pytest.raises(ValueError):
        await fetch({"data": {"id": identity, "name": "Official"}})


@pytest.mark.parametrize("identity", [None, True, 758, "", "0", "-1", " 758", "٧٥٨", "9" * 161])
async def test_invalid_requested_id_before_http(identity):
    with pytest.raises(ValueError):
        await fetch({}, player=identity)


@pytest.mark.parametrize(
    "payload",
    [{}, {"data": None}, {"data": []}, {"data": {}}, {"error": "secret-test-token", "data": {}}],
)
async def test_invalid_envelope(payload):
    with pytest.raises(ValueError) as error:
        await fetch(payload)
    assert "secret-test-token" not in str(error.value)


@pytest.mark.parametrize("status", [401, 403, 429, 500])
async def test_http_error_is_sanitized(status):
    with pytest.raises(RuntimeError) as error:
        await fetch({"body": "secret-test-token"}, status=status)
    assert "secret-test-token" not in str(error.value)


async def test_transport_error_is_sanitized():
    def handler(request):
        raise httpx.ConnectError("secret-test-token", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError, match="^Sportmonks request failed$"):
            await SportmonksProvider(
                api_key="secret-test-token", client=client
            ).fetch_player_identity(
                athlete_external_id="758",
            )


@pytest.mark.parametrize(
    "field,value",
    [
        ("external_id", "x" * 161),
        ("external_id", False),
        ("external_id", "\x00"),
        ("fetched_at", None),
        ("fetched_at", datetime(2026, 1, 1)),
    ],
)
def test_generic_contract(field, value):
    values = dict(external_id="opaque:player", name="Official", fetched_at=datetime.now(UTC))
    values[field] = value
    with pytest.raises(ValueError):
        ProviderPlayerIdentity(**values)


@pytest.mark.parametrize("targets", [(), [], (None,), ("team",)])
async def test_invalid_discovery_targets_before_database(targets):
    from unittest.mock import AsyncMock

    from app.sms24.player_identity_discovery import PlayerIdentityDiscovery
    from app.sms24.providers.registry import ProviderRegistry

    session = AsyncMock()
    service = PlayerIdentityDiscovery(session=session, registry=ProviderRegistry())
    with pytest.raises(ValueError):
        await service.run(targets=targets, reference_date=datetime.now(UTC).date())
    session.get.assert_not_awaited()
