"""Player Transfers using supplied Sportmonks evidence and mocked HTTP only."""

import traceback
from copy import deepcopy
from datetime import UTC, date, datetime

import httpx
import pytest

from app.sms24.providers.sportmonks import SportmonksProvider
from app.sms24.providers.transfers import build_transfer_observation_key

PLAYER = "37527758"
TOKEN = "private-test-token"


def transfer(**changes):
    return {
        "id": 112,
        "sport_id": 1,
        "player_id": 37527758,
        "type_id": 219,
        "from_team_id": 6067,
        "to_team_id": 260131,
        "position_id": 27,
        "detailed_position_id": 151,
        "date": "2025-01-30",
        "career_ended": False,
        "completed": True,
        "amount": None,
        **changes,
    }


def envelope(items, page=1, more=False):
    return {
        "data": items,
        "pagination": {
            "count": len(items),
            "per_page": 50,
            "has_more": more,
            "current_page": page,
            "next_page": "https://untrusted.invalid/private" if more else None,
            "next_cursor": "opaque-cursor" if more else None,
        },
    }


async def fetch(payload, *, player=PLAYER, max_pages=100):
    def handler(request):
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await SportmonksProvider(
            api_key=TOKEN, client=client, max_pages=max_pages
        ).fetch_transfers(athlete_external_id=player)


async def test_single_page_exact_request_mapping_and_stable_identity():
    raw = transfer(extra_provider_fact={"unknown": None})
    before = deepcopy(raw)

    def handler(request):
        assert request.url.path == f"/v3/football/transfers/players/{PLAYER}"
        assert dict(request.url.params) == {"page": "1", "per_page": "50"}
        assert request.headers["Authorization"] == TOKEN
        assert TOKEN not in str(request.url)
        return httpx.Response(200, json=envelope([raw]))

    started = datetime.now(UTC)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SportmonksProvider(api_key=TOKEN, client=client).fetch_transfers(
            athlete_external_id=PLAYER
        )
        assert not client.is_closed
    assert started <= result.fetched_at <= datetime.now(UTC)
    assert isinstance(result.transfers, tuple)
    (row,) = result.transfers
    assert row.external_id == "112" and row.athlete_external_id == PLAYER
    assert row.record_reference is None
    assert row.from_team_external_id == "6067" and row.to_team_external_id == "260131"
    assert row.reported_date == date(2025, 1, 30) and row.reported_type == "219"
    assert row.metadata == before and raw == before
    assert row.metadata["amount"] is None and row.metadata["completed"] is True
    assert (
        row.source_updated_at is row.athlete_name is row.from_team_name is row.to_team_name is None
    )
    changed = SportmonksProvider._normalize_transfer(
        transfer(player_id=9, date="2026-01-01", from_team_id=None, to_team_id=8, type_id=999)
    )
    assert build_transfer_observation_key(row) == build_transfer_observation_key(changed)
    different = SportmonksProvider._normalize_transfer(transfer(id=113))
    assert build_transfer_observation_key(row) != build_transfer_observation_key(different)


async def test_multiple_pages_reconstructed_locally():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == "api.sportmonks.com"
        assert request.url.path == f"/v3/football/transfers/players/{PLAYER}"
        assert set(request.url.params) == {"page", "per_page"}
        page = int(request.url.params["page"])
        return httpx.Response(200, json=envelope([transfer(id=page)], page, page < 3))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SportmonksProvider(api_key=TOKEN, client=client).fetch_transfers(
            athlete_external_id=PLAYER
        )
    assert [row.external_id for row in result.transfers] == ["1", "2", "3"]
    assert len(calls) == 3


async def test_empty_valid_result():
    assert (await fetch(envelope([]))).transfers == ()


@pytest.mark.parametrize("amount", [None, 0, 120000, "undisclosed"])
async def test_amount_and_unknown_fields_preserved_without_inference(amount):
    raw = {"id": 112, "player_id": int(PLAYER), "amount": amount}
    (row,) = (await fetch(envelope([raw]))).transfers
    assert row.metadata == raw
    assert row.metadata["amount"] == amount
    assert row.reported_type is row.reported_date is None
    assert row.from_team_external_id is row.to_team_external_id is None
    assert "completed" not in row.metadata


@pytest.mark.parametrize("field", ["id", "player_id"])
@pytest.mark.parametrize("value", [None, True, False, 1.2, {}, [], "", " ", "secret", -1, 0])
async def test_invalid_required_identifiers(field, value):
    with pytest.raises(ValueError):
        await fetch(envelope([transfer(**{field: value})]))


@pytest.mark.parametrize("field", ["id", "player_id"])
async def test_missing_required_identifiers(field):
    raw = transfer()
    del raw[field]
    with pytest.raises(ValueError):
        await fetch(envelope([raw]))


async def test_wrong_player_rejected_not_repaired():
    with pytest.raises(ValueError, match="does not match"):
        await fetch(envelope([transfer(player_id=123)]))


@pytest.mark.parametrize(
    "value",
    ["2025-02-30", "20250130", "2025-W05-4", "2025-01-30T00:00:00Z", "secret", "", 123, True, {}],
)
async def test_invalid_date_sanitized(value):
    with pytest.raises(ValueError, match="invalid transfer date") as caught:
        await fetch(envelope([transfer(date=value)]))
    assert "secret" not in "".join(traceback.format_exception(caught.value))


async def test_null_optional_facts():
    (row,) = (
        await fetch(
            envelope([transfer(date=None, type_id=None, from_team_id=None, to_team_id=None)])
        )
    ).transfers
    assert row.reported_date is row.reported_type is None
    assert row.from_team_external_id is row.to_team_external_id is None


@pytest.mark.parametrize(
    "player",
    [
        None,
        37527758,
        True,
        "",
        " ",
        "../1",
        "1?api_token=secret",
        "1/2",
        "-1",
        "0",
        "１",
        "x" * 161,
    ],
)
async def test_invalid_target_never_calls_http(player):
    def handler(request):
        pytest.fail("Invalid target must not cause HTTP")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError):
            await SportmonksProvider(api_key=TOKEN, client=client).fetch_transfers(
                athlete_external_id=player
            )


@pytest.mark.parametrize("failure", [401, 403, 429, 500, 302, "timeout", "json", "api", "envelope"])
async def test_http_and_api_errors_sanitized(failure, caplog):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout(TOKEN, request=request)
        if isinstance(failure, int):
            return httpx.Response(
                failure, text=TOKEN, headers={"Location": "https://untrusted.invalid/" + TOKEN}
            )
        if failure == "json":
            return httpx.Response(200, text=TOKEN)
        return httpx.Response(
            200, json={"data": [], "errors": TOKEN} if failure == "api" else {"data": TOKEN}
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        with pytest.raises((RuntimeError, ValueError)) as caught:
            await SportmonksProvider(api_key=TOKEN, client=client).fetch_transfers(
                athlete_external_id=PLAYER
            )
    assert TOKEN not in "".join(traceback.format_exception(caught.value))
    assert TOKEN not in caplog.text


@pytest.mark.parametrize(
    "pagination",
    [
        None,
        {},
        [],
        {"has_more": False},
        {"current_page": 1},
        {"current_page": True, "has_more": False},
        {"current_page": "1", "has_more": False},
        {"current_page": 2, "has_more": False},
        {"current_page": 1, "has_more": 0},
    ],
)
async def test_malformed_pagination_rejected(pagination):
    with pytest.raises(ValueError, match="pagination"):
        await fetch({"data": [transfer()], "pagination": pagination})


@pytest.mark.parametrize("failure", ["duplicate", "limit", "empty_more", "disappeared"])
async def test_pagination_termination_and_no_partial_success(failure):
    calls = []

    def handler(request):
        page = int(request.url.params["page"])
        calls.append(page)
        payload = envelope([transfer(id=112 if failure == "duplicate" else page)], page, True)
        if failure == "empty_more":
            payload["data"] = []
        elif failure == "disappeared" and page == 2:
            del payload["pagination"]
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises((ValueError, RuntimeError)):
            await SportmonksProvider(api_key=TOKEN, client=client, max_pages=2).fetch_transfers(
                athlete_external_id=PLAYER
            )
    assert calls == ([1] if failure == "empty_more" else [1, 2])
