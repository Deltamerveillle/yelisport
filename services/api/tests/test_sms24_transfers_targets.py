"""Automatic targets: mocked team HTTP, active membership validation and bounded batches."""

from datetime import date, datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.sms24.providers.sportmonks import SportmonksProvider
from app.sms24.transfers_batch import TransfersBatchOrchestrator
from app.sms24.transfers_runner import (
    TransfersAllProvidersFailed,
    TransfersProviderAttempt,
    TransfersRunnerResult,
)
from app.sms24.transfers_targets import SportmonksTransfersTargetDiscovery

DAY = date(2026, 9, 20)


def membership(**changes):
    return {
        "id": 1417302,
        "transfer_id": 541407,
        "player_id": 37337109,
        "team_id": 62,
        "start": "2026-01-14",
        "end": "2029-06-30",
        **changes,
    }


@pytest.fixture(autouse=True)
def no_real_http(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("Real HTTP forbidden")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)


async def discover_payload(payload):
    def handler(request):
        assert request.url.path == "/v3/football/teams/62"
        assert dict(request.url.params) == {"include": "players"}
        assert request.headers["Authorization"] == "secret-token"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await SportmonksProvider(
            api_key="secret-token", client=client
        ).fetch_team_player_ids(team_external_id="62", reference_date=DAY)


@pytest.mark.parametrize(
    "start,end,active",
    [
        ("2026-01-14", "2029-06-30", True),
        ("2026-09-20", "2026-09-20", True),
        (None, None, True),
        (None, "2026-09-20", True),
        ("2026-09-20", None, True),
        (None, "2026-09-19", False),
        ("2026-09-21", None, False),
    ],
)
async def test_active_membership_dates(start, end, active):
    result = await discover_payload(
        {"data": {"id": 62, "players": [membership(start=start, end=end)]}}
    )
    assert result == (("37337109",) if active else ())


async def test_deduplicated_ids_ignore_membership_and_transfer_identity():
    result = await discover_payload(
        {
            "data": {
                "id": 62,
                "players": [
                    membership(player_id=3),
                    membership(id=8, transfer_id=9, player_id=3),
                    membership(player_id=11),
                ],
            }
        }
    )
    assert result == ("11", "3")  # Opaque strings, not numeric ordering.


async def test_empty_players_is_valid():
    assert await discover_payload({"data": {"id": 62, "players": []}}) == ()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": None},
        {"data": []},
        {"data": {}},
        {"data": {"id": 62}},
        {"data": {"id": 62, "players": None}},
        {"data": {"id": 62, "players": {}}},
        {"data": {"id": 62, "players": [None]}},
        {"data": {"id": 53, "players": []}},
    ],
)
async def test_malformed_team_payload(payload):
    with pytest.raises(ValueError):
        await discover_payload(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("start", "2026-02-30"),
        ("end", "20260920"),
        ("start", "2026-W38-7"),
        ("end", "2026-09-20T00:00:00Z"),
        ("start", True),
        ("end", ""),
        ("start", "secret-token"),
        ("team_id", 53),
        ("team_id", None),
        ("player_id", None),
        ("player_id", True),
        ("player_id", 0),
        ("player_id", -1),
        ("player_id", 1.2),
        ("player_id", "１"),
        ("player_id", "x" * 161),
        ("player_id", "3/4"),
        ("player_id", ""),
        ("player_id", {}),
    ],
)
async def test_bad_membership_rejects_entire_payload(field, value):
    # Even after a valid row, no partial targets escape.
    with pytest.raises(ValueError) as caught:
        await discover_payload(
            {"data": {"id": 62, "players": [membership(player_id=9), membership(**{field: value})]}}
        )
    assert "secret-token" not in str(caught.value)


@pytest.mark.parametrize("field", ["start", "end", "player_id", "team_id"])
async def test_missing_membership_field(field):
    row = membership()
    del row[field]
    with pytest.raises(ValueError):
        await discover_payload({"data": {"id": 62, "players": [row]}})


async def test_inverted_dates_rejected():
    with pytest.raises(ValueError):
        await discover_payload(
            {"data": {"id": 62, "players": [membership(start="2026-09-21", end="2026-09-19")]}}
        )


@pytest.mark.parametrize("failure", [401, 403, 429, 500, 302, "transport", "api", "json"])
async def test_team_errors_sanitized(failure, caplog):
    def handler(request):
        if failure == "transport":
            raise httpx.ReadTimeout("secret-token", request=request)
        if isinstance(failure, int):
            return httpx.Response(
                failure, text="secret-token", headers={"Location": "https://private/secret-token"}
            )
        if failure == "json":
            return httpx.Response(200, text="secret-token")
        return httpx.Response(200, json={"data": {}, "errors": "secret-token"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        with pytest.raises((ValueError, RuntimeError)) as caught:
            await SportmonksProvider(api_key="secret-token", client=client).fetch_team_player_ids(
                team_external_id="62", reference_date=DAY
            )
    assert "secret-token" not in str(caught.value) + caplog.text


@pytest.mark.parametrize("team,day", [("../62", DAY), (True, DAY), ("62", datetime(2026, 9, 20))])
async def test_invalid_discovery_request_never_calls_http(team, day):
    provider = SportmonksProvider(api_key="secret-token")
    with pytest.raises(ValueError):
        await provider.fetch_team_player_ids(team_external_id=team, reference_date=day)


async def test_batch_deduplicates_bounds_continues_and_counts_exactly():
    error = TransfersAllProvidersFailed([])
    error.args = ("secret-token https://private",)
    runner = AsyncMock()
    runner.run.side_effect = [
        error,
        TransfersRunnerResult(
            [TransfersProviderAttempt("sportmonks", True, observations_processed=4)]
        ),
    ]
    batch = TransfersBatchOrchestrator(runner=runner, max_players=2)
    result = await batch.run(player_ids=["3", "2", "11", "2", "3"])
    assert [call.kwargs for call in runner.run.await_args_list] == [
        {"targets": {"sportmonks": "11"}},
        {"targets": {"sportmonks": "2"}},
    ]
    assert (
        result.targets_discovered,
        result.targets_attempted,
        result.targets_succeeded,
        result.targets_failed,
        result.targets_deferred,
        result.observations_processed,
    ) == (3, 2, 1, 1, 1, 4)
    assert result.attempts[0].reason == "transfers_target_failed"
    assert "secret-token" not in repr(result)


async def test_batch_empty_and_all_failed_have_explicit_counts():
    runner = AsyncMock()
    batch = TransfersBatchOrchestrator(runner=runner)
    empty = await batch.run(player_ids=[])
    assert empty.targets_discovered == empty.targets_attempted == empty.observations_processed == 0
    runner.run.assert_not_awaited()
    runner.run.side_effect = TransfersAllProvidersFailed([])
    result = await batch.run(player_ids=["2", "1"])
    assert result.targets_failed == 2 and result.targets_succeeded == 0


async def test_batch_propagates_database_error():
    runner = AsyncMock()
    runner.run.side_effect = SQLAlchemyError("database error")
    with pytest.raises(SQLAlchemyError):
        await TransfersBatchOrchestrator(runner=runner).run(player_ids=["1", "2"])
    assert runner.run.await_count == 1


@pytest.mark.parametrize("players", ["62", [True], ["0"], ["１"], ["1", "bad"], [1]])
async def test_batch_validates_all_ids_before_ingestion(players):
    runner = AsyncMock()
    with pytest.raises(ValueError):
        await TransfersBatchOrchestrator(runner=runner).run(player_ids=players)
    runner.run.assert_not_awaited()


@pytest.mark.parametrize("limit", [0, -1, True, 1.2])
def test_limits_must_be_positive_integers(limit):
    with pytest.raises(ValueError):
        TransfersBatchOrchestrator(runner=AsyncMock(), max_players=limit)
    with pytest.raises(ValueError):
        SportmonksTransfersTargetDiscovery(
            session=AsyncMock(), registry=AsyncMock(), max_teams=limit
        )


@pytest.mark.parametrize("limit", [50, 100, 200])
async def test_player_cursor_pages_cover_entire_stable_set(limit):
    players = [str(number) for number in range(1, 151)]
    runner = AsyncMock()
    runner.run.return_value = TransfersRunnerResult([TransfersProviderAttempt("sportmonks", True)])
    batch = TransfersBatchOrchestrator(runner=runner, max_players=limit)
    cursor = None
    visited = []
    while True:
        result = await batch.run(
            player_ids=list(reversed(players)) + players, after_player_external_id=cursor
        )
        page = [attempt.athlete_external_id for attempt in result.attempts]
        assert not set(visited).intersection(page)
        assert result.targets_discovered == 150
        assert result.targets_before_cursor == len(visited)
        visited.extend(page)
        assert result.targets_deferred == 150 - len(visited)
        assert result.has_more == (len(visited) < 150)
        if not result.has_more:
            assert result.next_cursor is None
            break
        assert result.next_cursor == page[-1]
        cursor = result.next_cursor
    assert visited == sorted(players)
    assert runner.run.await_count == 150


async def test_player_cursor_survives_removed_key_and_new_ids():
    runner = AsyncMock()
    runner.run.return_value = TransfersRunnerResult([])
    batch = TransfersBatchOrchestrator(runner=runner, max_players=2)
    first = await batch.run(player_ids=["1", "3", "5", "7"])
    assert first.next_cursor == "3"
    second = await batch.run(
        player_ids=["1", "2", "4", "5", "7"], after_player_external_id=first.next_cursor
    )
    assert [a.athlete_external_id for a in second.attempts] == ["4", "5"]
    assert second.targets_before_cursor == 2 and second.targets_deferred == 1
    end = await batch.run(player_ids=["1", "2"], after_player_external_id="9")
    assert end.targets_attempted == end.targets_deferred == 0
    assert end.next_cursor is None


async def test_failed_player_still_advances_cursor():
    runner = AsyncMock()
    runner.run.side_effect = TransfersAllProvidersFailed([])
    batch = TransfersBatchOrchestrator(runner=runner, max_players=1)
    first = await batch.run(player_ids=["1", "2"])
    assert first.targets_failed == 1 and first.next_cursor == "1"
    second = await batch.run(player_ids=["1", "2"], after_player_external_id=first.next_cursor)
    assert second.attempts[0].athlete_external_id == "2" and second.next_cursor is None


@pytest.mark.parametrize("cursor", ["", 1, True, "../1", "１", "0", "1" * 161])
async def test_invalid_cursors_rejected_before_any_io(cursor):
    from app.sms24.transfers_batch import AutomaticTransfersCursor

    runner, session, registry = AsyncMock(), AsyncMock(), AsyncMock()
    with pytest.raises(ValueError):
        await TransfersBatchOrchestrator(runner=runner).run(
            player_ids=["1"], after_player_external_id=cursor
        )
    with pytest.raises(ValueError):
        await SportmonksTransfersTargetDiscovery(session=session, registry=registry).discover(
            reference_date=DAY, after_team_external_id=cursor
        )
    with pytest.raises(ValueError):
        AutomaticTransfersCursor(after_player_external_id=cursor)
    with pytest.raises(ValueError):
        AutomaticTransfersCursor(after_team_external_id=cursor)
    runner.run.assert_not_awaited()
    assert session.mock_calls == registry.mock_calls == []
