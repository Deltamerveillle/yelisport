"""Local-only contract tests for the optional ESPN adapter."""

from datetime import UTC, datetime

import httpx
import pytest

from app.sms24.providers.espn import ESPNProvider

PAYLOAD = {
    "leagues": [
        {
            "id": "700",
            "name": "English Premier League",
            "slug": "eng.1",
            "season": {"displayName": "2026-27 English Premier League"},
        }
    ],
    "events": [
        {
            "id": "401878771",
            "date": "2026-10-17T11:30Z",
            "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED"}},
            "competitions": [
                {
                    "venue": {"fullName": "Hill Dickinson Stadium"},
                    "competitors": [
                        {
                            "team": {"id": "368", "displayName": "Everton"},
                            "homeAway": "home",
                            "score": "0",
                        },
                        {
                            "team": {"id": "363", "displayName": "Chelsea"},
                            "homeAway": "away",
                            "score": "0",
                        },
                    ],
                }
            ],
        }
    ],
}


def test_normalization_does_not_present_pre_match_zero_as_score():
    fixture = ESPNProvider.normalize_event(PAYLOAD["events"][0], PAYLOAD["leagues"][0])
    assert fixture.external_id == "401878771"
    assert fixture.status == "scheduled"
    assert fixture.competition.name == "English Premier League"
    assert [p.role for p in fixture.participants] == ["home", "away"]
    assert fixture.result["goals"] == {"home": None, "away": None}


@pytest.mark.asyncio
async def test_fetch_and_live_only_filter():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=PAYLOAD)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ESPNProvider(client=client)
        result = await provider.fetch_fixtures(sport_slug="football")
        assert result.raw_count == 1
        assert len(result.fixtures) == 1
        live_result = await provider.fetch_fixtures(live_only=True)
        assert live_result.fixtures == []
        assert (await provider.check_health()).is_healthy


@pytest.mark.asyncio
async def test_unsupported_sport_and_timezone_validation():
    provider = ESPNProvider()
    assert (await provider.fetch_fixtures(sport_slug="basketball")).fixtures == []
    with pytest.raises(ValueError, match="timezone"):
        await provider.fetch_fixtures(starts_from=datetime(2026, 10, 17))
    with pytest.raises(ValueError, match="starts_from"):
        await provider.fetch_fixtures(
            starts_from=datetime(2026, 10, 18, tzinfo=UTC),
            starts_until=datetime(2026, 10, 17, tzinfo=UTC),
        )
