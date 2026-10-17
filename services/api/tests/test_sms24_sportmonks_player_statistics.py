"""Season statistics adapter: mocked HTTP, opaque IDs and no human domain access."""

import ast
import inspect
import traceback
from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest

from app.sms24.providers import sportmonks
from app.sms24.providers.player_statistics import build_player_statistic_observation_key
from app.sms24.providers.sportmonks import SportmonksProvider

TOKEN = "private-statistics-token"
PLAYER = "758"


def detail(**changes):
    return {
        "id": 23799175,
        "player_statistic_id": 27324842,
        "type_id": 52,
        "value": {"total": 1, "goals": 1, "penalties": 0},
        "type": {
            "id": 52,
            "name": "Goals",
            "code": "goals",
            "developer_name": "GOALS",
            "model_type": "statistic",
            "stat_group": "offensive",
        },
        **changes,
    }


def statistic(**changes):
    return {
        "id": 27324842,
        "player_id": 758,
        "team_id": 62,
        "season_id": 825,
        "has_values": True,
        "position_id": 25,
        "jersey_number": 2,
        "details": [detail()],
        **changes,
    }


def envelope(**changes):
    return {"data": {"id": 758, "name": "James Tavernier", "statistics": [statistic()], **changes}}


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("Real HTTP is forbidden")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)


async def fetch(payload, player=PLAYER):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload),
        )
    ) as client:
        return await SportmonksProvider(api_key=TOKEN, client=client).fetch_player_statistics(
            athlete_external_id=player,
        )


async def test_real_shaped_payload_exact_mapping_and_request():
    raw = envelope()
    raw["data"]["statistics"][0].update(api_token=TOKEN, user_id="not-an-SMS-identity")
    before = deepcopy(raw)
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.path == "/v3/football/players/758"
        assert dict(request.url.params) == {"include": "statistics.details.type"}
        assert request.headers["Authorization"] == TOKEN
        assert TOKEN not in str(request.url)
        return httpx.Response(200, json=raw)

    started = datetime.now(UTC)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SportmonksProvider(api_key=TOKEN, client=client).fetch_player_statistics(
            athlete_external_id=PLAYER,
        )
        assert not client.is_closed
    assert len(calls) == 1 and type(result.statistics) is tuple
    assert started <= result.fetched_at <= datetime.now(UTC)
    (row,) = result.statistics
    assert row.external_id == "27324842" and row.athlete_external_id == PLAYER
    assert row.athlete_name == "James Tavernier" and row.scope == "season"
    assert row.record_reference is row.fixture_external_id is row.period_label is None
    assert row.source_updated_at is None
    assert row.metrics == {
        "52": {
            "detail_id": 23799175,
            "type_id": 52,
            "value": {"total": 1, "goals": 1, "penalties": 0},
            "name": "Goals",
            "code": "goals",
            "developer_name": "GOALS",
            "model_type": "statistic",
            "stat_group": "offensive",
        }
    }
    assert row.metadata == {
        "team_id": 62,
        "season_id": 825,
        "position_id": 25,
        "jersey_number": 2,
        "has_values": True,
    }
    assert raw == before


async def test_existing_get_json_is_used(monkeypatch):
    provider = SportmonksProvider(api_key=TOKEN)
    mocked = AsyncMock(return_value=envelope())
    monkeypatch.setattr(provider, "_get_json", mocked)
    await provider.fetch_player_statistics(athlete_external_id=PLAYER)
    mocked.assert_awaited_once_with(
        "/players/758",
        params={"include": "statistics.details.type"},
        data_type=dict,
    )


async def test_identity_independent_of_context_metrics_and_names():
    first = (await fetch(envelope())).statistics[0]
    changed = (
        await fetch(
            envelope(
                name="Other",
                statistics=[
                    statistic(
                        team_id=99,
                        season_id=44,
                        details=[detail(value=None)],
                    )
                ],
            )
        )
    ).statistics[0]
    assert build_player_statistic_observation_key(first) == build_player_statistic_observation_key(
        changed
    )
    assert first.metadata != changed.metadata and changed.metrics["52"]["value"] is None


@pytest.mark.parametrize("name", [None, "", " ", 123, True, [], {}, "x" * 201, "bad\x00name"])
async def test_invalid_player_name_remains_unknown(name):
    assert (await fetch(envelope(name=name))).statistics[0].athlete_name is None


@pytest.mark.parametrize(
    "player", [None, 758, True, "", "0", "-1", "１", "1.2", "1/2", "758?token=secret", "x" * 161]
)
async def test_invalid_requested_id_never_calls_http(player, monkeypatch):
    provider = SportmonksProvider(api_key=TOKEN)
    mocked = AsyncMock()
    monkeypatch.setattr(provider, "_get_json", mocked)
    with pytest.raises(ValueError):
        await provider.fetch_player_statistics(athlete_external_id=player)
    mocked.assert_not_awaited()


@pytest.mark.parametrize("field", ["id", "player_id", "team_id", "season_id", "position_id"])
@pytest.mark.parametrize("value", [True, False, 0, -1, 1.2, "１", "", "0", "1" * 161])
async def test_malformed_statistics_ids(field, value):
    with pytest.raises(ValueError):
        await fetch(envelope(statistics=[statistic(**{field: value})]))


@pytest.mark.parametrize("field", ["id", "player_statistic_id", "type_id"])
@pytest.mark.parametrize("value", [None, True, 0, -1, 1.2, "１", ""])
async def test_malformed_detail_ids(field, value):
    with pytest.raises(ValueError):
        await fetch(envelope(statistics=[statistic(details=[detail(**{field: value})])]))


@pytest.mark.parametrize(
    "case", ["player", "statistic_player", "parent", "type", "duplicate_stat", "duplicate_type"]
)
async def test_inconsistent_or_duplicate_ids_fail_closed(case):
    raw = envelope()
    item = raw["data"]["statistics"][0]
    if case == "player":
        raw["data"]["id"] = 759
    elif case == "statistic_player":
        item["player_id"] = 759
    elif case == "parent":
        item["details"][0]["player_statistic_id"] = 44
    elif case == "type":
        item["details"][0]["type"]["id"] = 53
    elif case == "duplicate_stat":
        raw["data"]["statistics"].append(deepcopy(item))
    else:
        item["details"].append(detail(id=23799176))
    with pytest.raises(ValueError):
        await fetch(raw)


@pytest.mark.parametrize("value", [None, {}, "", 0, True])
async def test_statistics_and_details_must_be_lists(value):
    with pytest.raises(ValueError):
        await fetch(envelope(statistics=value))
    with pytest.raises(ValueError):
        await fetch(envelope(statistics=[statistic(details=value)]))


@pytest.mark.parametrize(
    "case",
    [
        "statistics",
        "details",
        "stat_id",
        "player_id",
        "detail_id",
        "detail_parent",
        "detail_type",
        "value",
        "player_data_id",
    ],
)
async def test_missing_required_fields(case):
    raw = envelope()
    item = raw["data"]["statistics"][0]
    target, key = {
        "statistics": (raw["data"], "statistics"),
        "details": (item, "details"),
        "stat_id": (item, "id"),
        "player_id": (item, "player_id"),
        "detail_id": (item["details"][0], "id"),
        "detail_parent": (item["details"][0], "player_statistic_id"),
        "detail_type": (item["details"][0], "type_id"),
        "value": (item["details"][0], "value"),
        "player_data_id": (raw["data"], "id"),
    }[case]
    del target[key]
    with pytest.raises(ValueError):
        await fetch(raw)


@pytest.mark.parametrize("value", [None, [], "bad", True])
async def test_non_objects_rejected(value):
    for raw in (
        {"data": value},
        envelope(statistics=[value]),
        envelope(statistics=[statistic(details=[value])]),
        envelope(statistics=[statistic(details=[detail(type=value)])]),
    ):
        with pytest.raises((ValueError, RuntimeError)):
            await fetch(raw)


@pytest.mark.parametrize(
    "value", [None, 0, False, "unknown", [0, None], {"total": 0, "unknown": None}]
)
async def test_json_value_preserved_exactly(value):
    row = (await fetch(envelope(statistics=[statistic(details=[detail(value=value)])]))).statistics[
        0
    ]
    assert type(row.metrics["52"]["value"]) is type(value)
    assert row.metrics["52"]["value"] == value


@pytest.mark.parametrize("value", [{1: 2}, {"bad": (1, 2)}, float("nan"), float("inf")])
def test_contract_rejects_non_native_or_non_finite_values(value):
    with pytest.raises(ValueError):
        SportmonksProvider._normalize_player_statistic(
            statistic(details=[detail(value=value)]), PLAYER, None
        )


@pytest.mark.parametrize("value", [True, False, "2", 2.0, -1, {}, []])
async def test_jersey_number_not_coerced(value):
    with pytest.raises(ValueError):
        await fetch(envelope(statistics=[statistic(jersey_number=value)]))


async def test_unknown_context_and_empty_results():
    assert (await fetch(envelope(statistics=[]))).statistics == ()
    row = (
        await fetch(
            envelope(
                statistics=[
                    statistic(
                        team_id=None,
                        season_id=None,
                        position_id=None,
                        jersey_number=None,
                        has_values=None,
                        details=[],
                    )
                ]
            )
        )
    ).statistics[0]
    assert row.metrics == {} and all(value is None for value in row.metadata.values())
    minimal = {"id": "27324842", "player_id": PLAYER, "details": []}
    assert (await fetch(envelope(statistics=[minimal]))).statistics[0].metadata == {}


async def test_type_optional_and_deterministic_order():
    first = detail(type_id=53, type={"id": "53", "name": None})
    second = detail()
    del second["type"]
    rows = []
    for details in ([first, second], [second, first]):
        rows.append((await fetch(envelope(statistics=[statistic(details=details)]))).statistics[0])
    assert rows[0].metrics == rows[1].metrics
    assert list(rows[0].metrics) == ["52", "53"]
    assert "name" not in rows[0].metrics["52"]
    assert rows[0].metrics["53"]["name"] is None


@pytest.mark.parametrize("failure", [401, 403, 429, 500, 302, "timeout", "json", "api"])
async def test_secret_safe_http_errors(failure, caplog):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout(TOKEN, request=request)
        if isinstance(failure, int):
            return httpx.Response(failure, text=TOKEN)
        if failure == "json":
            return httpx.Response(200, text=TOKEN)
        return httpx.Response(200, json={"data": {}, "errors": TOKEN})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises((ValueError, RuntimeError)) as caught:
            await SportmonksProvider(api_key=TOKEN, client=client).fetch_player_statistics(
                athlete_external_id=PLAYER,
            )
    assert TOKEN not in "".join(traceback.format_exception(caught.value))
    assert TOKEN not in caplog.text


def test_adapter_has_no_persistence_or_human_domain_imports():
    tree = ast.parse(inspect.getsource(sportmonks))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not node.module.startswith(("app.models", "app.db", "sqlalchemy"))
        if isinstance(node, ast.Name):
            assert node.id not in {
                "AthletePerformance",
                "User",
                "Profile",
                "Athlete",
                "SportsAthleteIdentityLink",
                "AsyncSession",
            }


@pytest.mark.parametrize(
    "changes",
    [
        {"has_values": 1},
        {"has_values": "true"},
        {"details": [detail(type={"id": True})]},
        {"details": [detail(type={"id": None})]},
        {"details": [detail(type={"name": 52})]},
        {"details": [detail(), detail(type_id="52")]},
    ],
)
async def test_invalid_flags_type_labels_and_normalized_duplicates(changes):
    with pytest.raises(ValueError):
        await fetch(envelope(statistics=[statistic(**changes)]))


async def test_multiple_observations_have_deterministic_order():
    first = statistic(id="2", details=[detail(player_statistic_id="2")])
    second = statistic(id=1, details=[])
    left = await fetch(envelope(statistics=[first, second]))
    right = await fetch(envelope(statistics=[second, first]))
    assert left.statistics == right.statistics
    assert [row.external_id for row in left.statistics] == ["1", "2"]
