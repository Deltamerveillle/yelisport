"""Sportmonks V3 contract tests. All HTTP traffic uses MockTransport."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.sms24.providers import ProviderCompetition, ProviderFixture, ProviderParticipant
from app.sms24.providers.sportmonks import SportmonksProvider

DAY = datetime(2026, 9, 9, tzinfo=timezone.utc)
TOKEN = "test-only-sportmonks-token"


def fixture_payload(state=5, goals=(2, 1), penalties=None):
    scores = []
    for description, values in (("CURRENT", goals), ("PENALTIES", penalties)):
        if values is not None:
            for participant_id, role, value in zip((11, 22), ("home", "away"), values):
                scores.append({"participant_id": participant_id, "description": description,
                               "score": {"participant": role, "goals": value}})
    return {
        "id": 123, "state_id": state, "starting_at": "2026-09-09 18:00:00",
        "last_processed_at": "2026-09-09 18:45:00",
        "participants": [
            {"id": 22, "name": "Away", "meta": {"location": "away"}},
            {"id": 11, "name": "Home", "meta": {"location": "home"}},
        ],
        "scores": scores, "periods": [{"minutes": 45}, {"minutes": 93}],
        "league": {"id": 7, "name": "League", "country": {"iso2": "ci"}},
        "season": {"name": "2026/2027"}, "venue": {"name": "Stadium"},
    }


def envelope(data=None, page=1, more=False):
    return {"data": [fixture_payload()] if data is None else data,
            "pagination": {"current_page": page, "has_more": more}}


@pytest.mark.asyncio
async def test_daily_request_and_normalization():
    def handler(request):
        assert request.headers["Authorization"] == TOKEN
        assert TOKEN not in str(request.url)
        assert request.url.path == "/v3/football/fixtures/date/2026-09-09"
        assert request.url.params["timezone"] == "UTC"
        assert request.url.params["page"] == "1"
        assert "participants" in request.url.params["include"]
        return httpx.Response(200, json=envelope())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SportmonksProvider(api_key=TOKEN, client=client).fetch_fixtures(
            starts_from=DAY, starts_until=DAY + timedelta(hours=23))
    fixture = result.fixtures[0]
    assert isinstance(fixture, ProviderFixture)
    assert isinstance(fixture.competition, ProviderCompetition)
    assert all(isinstance(p, ProviderParticipant) for p in fixture.participants)
    assert [p.external_id for p in fixture.participants] == ["11", "22"]
    assert [p.role for p in fixture.participants] == ["home", "away"]
    assert [p.position for p in fixture.participants] == [0, 1]
    assert [p.result_status for p in fixture.participants] == ["winner", "loser"]
    assert fixture.participants[0].score == {"value": 2}
    assert fixture.starts_at == DAY + timedelta(hours=18)
    assert fixture.source_updated_at == DAY + timedelta(hours=18, minutes=45)
    assert fixture.live_clock == "93"
    assert fixture.competition.country_code == "CI"
    assert fixture.competition.season == "2026/2027"
    assert result.raw_count == 1 and result.fetched_at.tzinfo == timezone.utc


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_key(key):
    with pytest.raises(ValueError, match="key is required"):
        SportmonksProvider(api_key=key)


@pytest.mark.asyncio
async def test_unsupported_sport_never_calls_http():
    def handler(request):
        pytest.fail("Unexpected HTTP request")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SportmonksProvider(api_key=TOKEN, client=client).fetch_fixtures(
            sport_slug="basketball")
    assert result.fixtures == [] and result.raw_count == 0


@pytest.mark.asyncio
async def test_live_empty_success_without_pagination():
    def handler(request):
        assert request.url.path.endswith("/livescores/inplay")
        assert "page" not in request.url.params
        return httpx.Response(200, json={"data": []})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SportmonksProvider(api_key=TOKEN, client=client).fetch_fixtures(live_only=True)
    assert result.fixtures == [] and result.raw_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "limit", "http", "duplicate", "invalid"])
async def test_pagination_is_complete_or_fails(failure):
    calls = []
    def handler(request):
        page = int(request.url.params["page"])
        calls.append(page)
        assert request.url.host == "api.sportmonks.com"
        if failure == "http" and page == 2:
            return httpx.Response(503)
        data = fixture_payload()
        data["id"] = 123 if failure == "duplicate" else page
        payload = envelope([data], page, page == 1 or failure == "limit")
        payload["pagination"]["next_page"] = "https://untrusted.test/never-follow"
        if failure == "invalid":
            payload["pagination"]["has_more"] = "true"
        return httpx.Response(200, json=payload)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SportmonksProvider(api_key=TOKEN, client=client, max_pages=2)
        if failure:
            with pytest.raises((ValueError, RuntimeError)):
                await provider.fetch_fixtures(starts_from=DAY)
        else:
            result = await provider.fetch_fixtures(starts_from=DAY)
            assert result.raw_count == 2
            assert [f.external_id for f in result.fixtures] == ["1", "2"]
    assert calls == ([1] if failure == "invalid" else [1, 2])


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", 401, 403, 429, 500, 503, "json", "list",
                                         "missing", "wrong_data", "error"])
async def test_errors_are_sanitized_and_health_fails(failure, caplog):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout(TOKEN, request=request)
        if isinstance(failure, int):
            return httpx.Response(failure, text=TOKEN)
        if failure == "json":
            return httpx.Response(200, text=TOKEN)
        payload = {"list": [], "missing": {"message": TOKEN},
                   "wrong_data": {"data": TOKEN},
                   "error": {"data": [], "errors": TOKEN}}[failure]
        return httpx.Response(200, json=payload)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SportmonksProvider(api_key=TOKEN, client=client)
        with pytest.raises((ValueError, RuntimeError)) as error:
            await provider.fetch_fixtures()
        assert TOKEN not in str(error.value)
        health = await provider.check_health()
    assert health.is_healthy is False
    assert TOKEN not in health.message and TOKEN not in caplog.text
    assert health.checked_at.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_health_empty_is_success():
    def handler(request):
        assert request.url.params["per_page"] == "1"
        assert "include" not in request.url.params
        return httpx.Response(200, json=envelope([]))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        health = await SportmonksProvider(api_key=TOKEN, client=client).check_health()
    assert health.is_healthy and health.latency_ms >= 0


@pytest.mark.parametrize("state,status", [
    (1, "scheduled"), (2, "live"), (3, "live"), (4, "live"), (5, "finished"),
    (6, "live"), (7, "finished"), (8, "finished"), (9, "live"), (10, "postponed"),
    (11, "suspended"), (12, "cancelled"), (13, "scheduled"), (14, "finished"),
    (15, "suspended"), (16, "scheduled"), (17, "finished"), (18, "suspended"),
    (19, "unknown"), (20, "cancelled"), (21, "live"), (22, "live"), (25, "live"),
    (26, "unknown"), (999, "unknown"), (None, "unknown"),
])
def test_states(state, status):
    fixture = SportmonksProvider(api_key=TOKEN)._normalize_fixture(fixture_payload(state))
    assert fixture.status == status


@pytest.mark.parametrize("state,goals,penalties,outcomes", [
    (5, (0, 0), None, ["draw", "draw"]),
    (5, (None, None), None, [None, None]),
    (2, (2, 1), None, [None, None]),
    (7, (3, 2), None, ["winner", "loser"]),
    (8, (1, 1), (4, 5), ["loser", "winner"]),
    (8, (1, 1), None, [None, None]),
])
def test_scores_and_outcomes(state, goals, penalties, outcomes):
    data = fixture_payload(state, goals, penalties)
    for team in data["participants"]:
        team["meta"]["winner"] = False if state == 5 else None
    fixture = SportmonksProvider(api_key=TOKEN)._normalize_fixture(data)
    assert [p.result_status for p in fixture.participants] == outcomes
    assert fixture.result["goals"] == dict(zip(("home", "away"), goals))
    if penalties:
        assert fixture.result["score"]["penalty"] == {"home": 4, "away": 5}
    if state == 7:
        assert fixture.result["score"]["extratime"] == {"home": 3, "away": 2}


def test_optional_data_absent():
    data = fixture_payload()
    for field in ("scores", "league", "season", "venue", "periods", "last_processed_at"):
        del data[field]
    fixture = SportmonksProvider(api_key=TOKEN)._normalize_fixture(data)
    assert fixture.competition is None and fixture.venue is None and fixture.live_clock is None
    assert fixture.participants[0].score == {"value": None}
    assert fixture.participants[0].result_status is None


@pytest.mark.parametrize("field,value", [("id", None), ("starting_at", "bad"),
    ("participants", []), ("participants", [{"meta": {}}]), ("scores", {})])
def test_invalid_required_data(field, value):
    data = fixture_payload()
    data[field] = value
    with pytest.raises(ValueError):
        SportmonksProvider(api_key=TOKEN)._normalize_fixture(data)


def test_duplicate_locations_are_rejected():
    data = fixture_payload()
    data["participants"][0]["meta"]["location"] = "home"
    with pytest.raises(ValueError):
        SportmonksProvider(api_key=TOKEN)._normalize_fixture(data)


@pytest.mark.parametrize("start,end", [(DAY.replace(tzinfo=None), None),
    (DAY, DAY + timedelta(days=1)), (DAY + timedelta(hours=1), DAY)])
@pytest.mark.asyncio
async def test_invalid_window_makes_no_request(start, end):
    def handler(request):
        pytest.fail("Unexpected request")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError):
            await SportmonksProvider(api_key=TOKEN, client=client).fetch_fixtures(
                starts_from=start, starts_until=end)


def test_timestamp_and_window_converted_to_utc():
    provider = SportmonksProvider(api_key=TOKEN)
    data = fixture_payload()
    data["starting_at"] = "2026-09-09T20:00:00+02:00"
    assert provider._normalize_fixture(data).starts_at == DAY + timedelta(hours=18)
    assert provider._day(datetime.fromisoformat("2026-09-10T00:30:00+02:00"), None) == "2026-09-09"


def test_country_display_name_is_preserved_as_sporting_jurisdiction():
    data = fixture_payload()
    data["league"]["country"] = {"iso2": "br", "name": " Brazil "}
    fixture = SportmonksProvider(api_key=TOKEN)._normalize_fixture(data)
    assert fixture.competition.country_code == "BR"
    assert fixture.competition.jurisdiction_name == "Brazil"
    assert all(participant.country_code is None for participant in fixture.participants)


@pytest.mark.parametrize(("country", "expected_name", "expected_code"), [
    ({"name": " Scotland ", "iso2": "GB"}, "Scotland", "GB"),
    (None, None, None),
    ({}, None, None),
    ({"name": "Scotland"}, "Scotland", None),
    ({"iso2": "gb"}, None, "GB"),
    ({"name": "  ", "iso2": "12"}, None, None),
    ({"name": 123, "iso2": "éé"}, None, None),
    ({"iso2": "GBR"}, None, None),
    ({"iso2": 12}, None, None),
    ("Scotland", None, None),
])
def test_incomplete_country_never_invents_context(country, expected_name, expected_code):
    data = fixture_payload()
    if country is None:
        data["league"].pop("country", None)
    else:
        data["league"]["country"] = country
    fixture = SportmonksProvider(api_key=TOKEN)._normalize_fixture(data)
    assert fixture.competition.jurisdiction_name == expected_name
    assert fixture.competition.country_code == expected_code
    assert all(participant.country_code is None for participant in fixture.participants)
