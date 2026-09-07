"""Tests for the SMS24 API-Football provider adapter."""

from datetime import datetime, timezone

import httpx
import pytest

from app.sms24.providers.api_football import (
    APIFootballProvider,
)


def fixture_payload(
    *,
    status: str = "FT",
):
    return {
        "fixture": {
            "id": 12345,
            "referee": "Test Referee",
            "timezone": "UTC",
            "date": "2026-09-07T18:00:00+00:00",
            "venue": {
                "name": "Stade Test",
                "city": "Abidjan",
            },
            "status": {
                "short": status,
                "elapsed": 90,
            },
        },
        "league": {
            "id": 777,
            "name": "SMS Test League",
            "country": "CI",
            "season": 2026,
            "round": "Round 1",
            "logo": "https://example.test/league.png",
        },
        "teams": {
            "home": {
                "id": 1,
                "name": "Team A",
                "logo": "https://example.test/a.png",
                "winner": True,
            },
            "away": {
                "id": 2,
                "name": "Team B",
                "logo": "https://example.test/b.png",
                "winner": False,
            },
        },
        "goals": {
            "home": 2,
            "away": 1,
        },
        "score": {
            "halftime": {
                "home": 1,
                "away": 0,
            },
            "fulltime": {
                "home": 2,
                "away": 1,
            },
        },
    }


@pytest.mark.asyncio
async def test_api_football_normalizes_fixture():
    async def handler(request):
        assert request.headers["x-apisports-key"] == "secret"

        return httpx.Response(
            200,
            json={
                "errors": [],
                "results": 1,
                "response": [
                    fixture_payload()
                ],
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )

    provider = APIFootballProvider(
        api_key="secret",
        client=client,
    )

    result = await provider.fetch_fixtures(
        sport_slug="football"
    )

    await client.aclose()

    assert result.raw_count == 1

    fixture = result.fixtures[0]

    assert fixture.external_id == "12345"
    assert fixture.sport_slug == "football"
    assert fixture.status == "finished"
    assert fixture.live_clock == "90"
    assert fixture.venue == "Stade Test, Abidjan"
    assert fixture.name == "Team A vs Team B"

    assert fixture.competition is not None
    assert fixture.competition.external_id == "777"
    assert fixture.competition.name == "SMS Test League"
    assert fixture.competition.country_code == "CI"

    assert len(fixture.participants) == 2

    home = fixture.participants[0]
    away = fixture.participants[1]

    assert home.external_id == "1"
    assert home.role == "home"
    assert home.score == {"value": 2}
    assert home.result_status == "winner"

    assert away.external_id == "2"
    assert away.role == "away"
    assert away.score == {"value": 1}
    assert away.result_status == "loser"


@pytest.mark.asyncio
async def test_api_football_live_uses_live_all():
    async def handler(request):
        assert request.url.params["live"] == "all"

        return httpx.Response(
            200,
            json={
                "errors": [],
                "results": 0,
                "response": [],
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )

    provider = APIFootballProvider(
        api_key="secret",
        client=client,
    )

    result = await provider.fetch_fixtures(
        live_only=True
    )

    await client.aclose()

    assert result.fixtures == []
    assert result.raw_count == 0


@pytest.mark.asyncio
async def test_api_football_single_day_uses_date_param():
    async def handler(request):
        assert request.url.params["date"] == "2026-09-07"
        assert "from" not in request.url.params
        assert "to" not in request.url.params

        return httpx.Response(
            200,
            json={
                "errors": [],
                "results": 0,
                "response": [],
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )

    provider = APIFootballProvider(
        api_key="secret",
        client=client,
    )

    await provider.fetch_fixtures(
        starts_from=datetime(
            2026,
            9,
            7,
            0,
            0,
            tzinfo=timezone.utc,
        ),
        starts_until=datetime(
            2026,
            9,
            7,
            23,
            59,
            59,
            tzinfo=timezone.utc,
        ),
    )

    await client.aclose()


@pytest.mark.asyncio
async def test_api_football_rejects_multi_day_global_range():
    provider = APIFootballProvider(
        api_key="secret",
    )

    with pytest.raises(
        ValueError,
        match="one calendar day at a time",
    ):
        await provider.fetch_fixtures(
            starts_from=datetime(
                2026,
                9,
                7,
                tzinfo=timezone.utc,
            ),
            starts_until=datetime(
                2026,
                9,
                8,
                23,
                59,
                tzinfo=timezone.utc,
            ),
        )


@pytest.mark.asyncio
async def test_api_football_unknown_status_becomes_unknown():
    async def handler(request):
        return httpx.Response(
            200,
            json={
                "errors": [],
                "results": 1,
                "response": [
                    fixture_payload(
                        status="NEW_STATUS"
                    )
                ],
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )

    provider = APIFootballProvider(
        api_key="secret",
        client=client,
    )

    result = await provider.fetch_fixtures()

    await client.aclose()

    assert result.fixtures[0].status == "unknown"


@pytest.mark.asyncio
async def test_api_football_health_success():
    async def handler(request):
        assert request.url.path == "/status"

        return httpx.Response(
            200,
            json={
                "errors": [],
                "response": {
                    "account": {
                        "firstname": "SMS",
                        "lastname": "Test",
                    }
                },
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )

    provider = APIFootballProvider(
        api_key="secret",
        client=client,
    )

    health = await provider.check_health()

    await client.aclose()

    assert health.is_healthy is True
    assert health.checked_at.tzinfo is not None


def test_api_football_rejects_empty_key():
    with pytest.raises(
        ValueError,
        match="API-Football API key is required",
    ):
        APIFootballProvider(
            api_key="   "
        )
