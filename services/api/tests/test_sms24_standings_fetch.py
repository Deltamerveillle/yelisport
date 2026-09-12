"""Mocked HTTP tests for standings fetch; no external provider calls."""

from datetime import UTC, datetime

import httpx
import pytest

from app.sms24.providers.api_football import APIFootballProvider
from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.sportmonks import SportmonksProvider
from tests.test_sms24_standings_normalization import api_row, sportmonks_row


def api_payload(rows=None):
    return {
        "errors": [],
        "response": [
            {
                "league": {
                    "id": 7,
                    "season": 2026,
                    "standings": [rows if rows is not None else [api_row()]],
                }
            }
        ],
    }


def sm_payload(rows=None, page=1, more=False):
    return {
        "data": rows if rows is not None else [sportmonks_row()],
        "pagination": {"current_page": page, "has_more": more},
    }


@pytest.mark.asyncio
async def test_api_football_fetch_preserves_supplied_stats_and_timestamps():
    def handler(request):
        assert request.url.path == "/standings"
        assert dict(request.url.params) == {"league": "7", "season": "2026"}
        assert request.headers["x-apisports-key"] == "test-token"
        return httpx.Response(200, json=api_payload())

    before = datetime.now(UTC)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await APIFootballProvider(api_key="test-token", client=client).fetch_standings(
            league_external_id="7",
            season="2026",
        )
        assert not client.is_closed
    assert before <= result.fetched_at <= datetime.now(UTC)
    assert result.fetched_at.utcoffset() is not None
    row = result.rows[0]
    assert row.external_competition_id == "7" and row.external_season_id == "2026"
    assert row.points == 9 and row.goal_difference == -2
    assert row.home_points is None and row.away_points is None
    assert row.provider_updated_at == datetime.fromisoformat("2026-09-11T12:00:00+02:00")
    assert row.provider_updated_at.utcoffset() is not None


@pytest.mark.asyncio
async def test_sportmonks_fetch_paginates_locally_and_preserves_real_rule():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        assert request.url.path == "/v3/football/standings/seasons/88"
        assert request.url.params["include"] == "participant;details.type;rule.type"
        assert request.headers["Authorization"] == "test-token"
        page = int(request.url.params["page"])
        raw = sportmonks_row()
        raw["id"] = page
        raw["details"] = [{"type_id": 999999, "value": {"unknown": True}}]
        payload = sm_payload([raw], page=page, more=page == 1)
        payload["pagination"]["next_page"] = "https://untrusted.invalid/never-follow"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SportmonksProvider(api_key="test-token", client=client).fetch_standings(
            season="88"
        )
    assert len(paths) == 2 and len(result.rows) == 2
    assert result.fetched_at.utcoffset() is not None
    assert result.rows[0].description == "UEFA Champions League"
    assert result.rows[0].home_points is None and result.rows[0].provider_updated_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"response": None},
        {"response": [None]},
        {"response": [{"league": {"id": 7, "season": 2026}}]},
        {"response": [{"league": {"id": 7, "season": 2026, "standings": [{}]}}]},
        {"response": [{"league": {"id": 8, "season": 2026, "standings": []}}]},
        api_payload([{"rank": 0}]),
    ],
)
async def test_api_malformed_envelopes_and_rows_fail_explicitly(payload):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(ValueError):
            await APIFootballProvider(api_key="test", client=client).fetch_standings(
                league_external_id="7", season="2026"
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": {}},
        sm_payload([{}]),
        sm_payload([], more=True),
        {"data": [], "pagination": {"current_page": 2, "has_more": False}},
    ],
)
async def test_sportmonks_malformed_data_and_pagination_fail(payload):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(ValueError):
            await SportmonksProvider(api_key="test", client=client).fetch_standings(season="88")


@pytest.mark.asyncio
async def test_sportmonks_standings_without_pagination_is_complete_first_page():
    payload = {"data": [sportmonks_row()]}

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        result = await SportmonksProvider(
            api_key="test",
            client=client,
        ).fetch_standings(
            season="88",
        )

    assert len(result.rows) == 1
    assert result.rows[0].external_season_id == "88"
    assert result.fetched_at.utcoffset() is not None


@pytest.mark.asyncio
async def test_sportmonks_empty_without_pagination_is_valid_success():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"data": []})
        )
    ) as client:
        result = await SportmonksProvider(
            api_key="test",
            client=client,
        ).fetch_standings(
            season="88",
        )

    assert result.rows == []
    assert result.fetched_at.utcoffset() is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["api", "sportmonks"])
async def test_empty_valid_result_is_explicit_success(provider):
    payload = {"response": []} if provider == "api" else sm_payload([])
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        adapter = (
            APIFootballProvider(api_key="test", client=client)
            if provider == "api"
            else SportmonksProvider(api_key="test", client=client)
        )
        result = await adapter.fetch_standings(
            season="2026" if provider == "api" else "88", league_external_id="7"
        )
    assert result.rows == [] and result.fetched_at.utcoffset() is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["api", "sportmonks"])
@pytest.mark.parametrize("failure", ["http", "transport", "json", "provider_error"])
async def test_fetch_failures_do_not_expose_upstream_secrets(provider, failure):
    def handler(request):
        if failure == "transport":
            raise httpx.ReadTimeout("private-secret", request=request)
        if failure == "json":
            return httpx.Response(200, text="private-secret")
        if failure == "provider_error":
            return httpx.Response(200, json={"errors": {"token": "private-secret"}})
        return httpx.Response(503, text="private-secret")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = (
            APIFootballProvider(api_key="test", client=client)
            if provider == "api"
            else SportmonksProvider(api_key="test", client=client)
        )
        with pytest.raises((ValueError, RuntimeError)) as error:
            await adapter.fetch_standings(season="88", league_external_id="7")
        assert "private-secret" not in str(error.value)


@pytest.mark.asyncio
async def test_sportmonks_duplicate_pages_and_wrong_season_are_rejected():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=sm_payload()))
    ) as client:
        with pytest.raises(ValueError, match="does not match"):
            await SportmonksProvider(api_key="test", client=client).fetch_standings(season="99")

    def repeated(request):
        return httpx.Response(200, json=sm_payload(page=int(request.url.params["page"]), more=True))

    async with httpx.AsyncClient(transport=httpx.MockTransport(repeated)) as client:
        with pytest.raises(ValueError, match="duplicate"):
            await SportmonksProvider(api_key="test", client=client).fetch_standings(season="88")


@pytest.mark.asyncio
@pytest.mark.parametrize("plan", ["Free plans cannot access this season: private-secret", None, ""])
async def test_api_football_plan_restriction_is_typed_and_safe(plan):
    payload = {"errors": {"plan": plan, "debug": "https://example.test?key=private-secret"}}
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        provider = APIFootballProvider(api_key="private-secret", client=client)
        with pytest.raises(ProviderAccessRestrictedError) as caught:
            await provider.fetch_standings(league_external_id="179", season="2026")
    error = caught.value
    assert error.code == "provider_access_restricted"
    assert str(error) == "provider_access_restricted"
    assert error.args == ("provider_access_restricted",)
    assert "private-secret" not in repr(error)
    assert "example.test" not in repr(error)
    assert error.__cause__ is None
