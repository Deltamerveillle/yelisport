"""Existing-team selection and composed ingestion on disposable PostgreSQL only."""

from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models.athlete import Athlete
from app.models.athlete_country_eligibility import AthleteCountryEligibility
from app.models.athlete_passport import AthletePassport
from app.models.sport import Sport
from app.models.sports_live import (
    SportsCanonicalCompetitor,
    SportsCompetitor,
    SportsDataSource,
    SportsDataSourceCapability,
)
from app.models.sports_transfers import (
    SportsAthleteIdentityLink,
    SportsCanonicalTransfer,
    SportsTransferObservation,
)
from app.models.user import User
from app.sms24 import runtime
from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.registry import ProviderRegistry
from app.sms24.providers.sportmonks import SportmonksProvider
from app.sms24.transfers import SMS24TransfersRepository
from app.sms24.transfers_targets import SportmonksTransfersTargetDiscovery
from tests import test_sms24_transfers_postgres as foundation
from tests.test_sms24_sportmonks_transfers import envelope, transfer
from tests.test_sms24_transfers_postgres import NOW, add
from tests.test_sms24_transfers_targets import DAY, membership

connection = foundation.connection
session = foundation.session


@pytest.fixture(autouse=True)
def forbidden_side_effects(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("Real HTTP and identity resolution are forbidden")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
    for method in ("create_event", "resolve_observation", "link_athlete"):
        monkeypatch.setattr(SMS24TransfersRepository, method, forbidden)


async def seed(session, teams=("62",)):
    sport = await add(session, Sport, slug="football", name="Football")
    source = await add(
        session,
        SportsDataSource,
        slug="sportmonks",
        name="Sportmonks",
        health_status="degraded",
        last_checked_at=NOW,
        last_success_at=NOW,
        last_failure_at=NOW,
    )
    cap = await add(
        session,
        SportsDataSourceCapability,
        source_id=source.id,
        capability="transfers",
        is_active=True,
    )
    for team in teams:
        await add(
            session,
            SportsCompetitor,
            sport_id=sport.id,
            source_id=source.id,
            external_id=team,
            competitor_type="team",
            name="Known team",
        )
    return sport, source, cap


async def snapshot(session):
    models = (
        SportsDataSource,
        SportsDataSourceCapability,
        SportsCompetitor,
        SportsCanonicalCompetitor,
        SportsCanonicalTransfer,
        User,
        Athlete,
        AthletePassport,
        AthleteCountryEligibility,
        SportsAthleteIdentityLink,
    )
    return [
        (await session.execute(select(model.__table__).order_by(model.id))).mappings().all()
        for model in models
    ]


async def test_known_team_discovery_is_read_only(session):
    await seed(session)
    before = await snapshot(session)
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.url.path == "/v3/football/teams/62"
        assert dict(request.url.params) == {"include": "players"}
        return httpx.Response(200, json={"data": {"id": 62, "players": [membership()]}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        registry = ProviderRegistry()
        registry.register(SportmonksProvider(api_key="test", client=client))
        result = await SportmonksTransfersTargetDiscovery(
            session=session, registry=registry
        ).discover(reference_date=DAY)
    assert result.player_ids == ("37337109",) and len(calls) == 1
    assert result.attempts[0].success
    assert await snapshot(session) == before


async def test_runtime_multi_team_bounded_dedup_batch_and_no_identity_mutations(
    session, monkeypatch
):
    sport, source, _ = await seed(session, ("734", "62", "53"))
    # Existing identities are preserved, and never used to identify discovered IDs.
    person = await foundation.human(session, sport)
    await add(session, AthletePassport, athlete_id=person.id, club_name="Unchanged")
    canonical = await foundation.canonical(session, sport)
    await add(session, SportsCanonicalTransfer, canonical_athlete_id=canonical.id)
    other = await add(session, SportsDataSource, slug="api-football", name="API")
    await add(
        session,
        SportsCompetitor,
        source_id=other.id,
        sport_id=sport.id,
        external_id="1",
        name="Other provider team",
        competitor_type="team",
    )
    # An athlete and a different sport are not teams eligible for discovery.
    await add(
        session,
        SportsCompetitor,
        source_id=source.id,
        sport_id=sport.id,
        external_id="0",
        name="Existing athlete",
        competitor_type="athlete",
    )
    tennis = await add(session, Sport, slug="tennis", name="Tennis")
    await add(
        session,
        SportsCompetitor,
        source_id=source.id,
        sport_id=tennis.id,
        external_id="01",
        name="Other sport",
        competitor_type="team",
    )
    await session.commit()
    before = await snapshot(session)
    paths = []

    def handler(request):
        path = request.url.path
        paths.append(path)
        if "/teams/" in path:
            team = int(path.rsplit("/", 1)[1])
            assert team in (53, 62)
            players = (2, 11) if team == 53 else (2, 3)
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": team,
                        "players": [
                            membership(team_id=team, player_id=player) for player in players
                        ],
                    }
                },
            )
        if "/fixtures/date/" in path:
            return httpx.Response(200, json={"data": []})
        assert "/transfers/players/" in path
        player = int(path.rsplit("/", 1)[1])
        if player == 11:
            return httpx.Response(500, text="secret upstream")
        assert player == 2
        return httpx.Response(200, json=envelope([transfer(player_id=player)]))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        registry = ProviderRegistry()
        registry.register(SportmonksProvider(api_key="test", client=client))
        monkeypatch.setattr(runtime, "build_sms24_provider_registry", lambda settings: registry)
        session.commit = AsyncMock(side_effect=AssertionError("Caller owns commit"))
        result = await runtime.run_sms24_automatic_transfers(
            session, reference_date=DAY, max_teams=2, max_players=2
        )
    assert paths[:2] == ["/v3/football/teams/53", "/v3/football/teams/62"]
    assert result.discovery.player_ids == ("11", "2", "3")
    assert result.discovery.teams_limited
    batch = result.batch
    assert (
        batch.targets_discovered,
        batch.targets_attempted,
        batch.targets_succeeded,
        batch.targets_failed,
        batch.targets_deferred,
        batch.observations_processed,
    ) == (3, 2, 1, 1, 1, 1)
    assert "secret" not in repr(result)
    observations = list(await session.scalars(select(SportsTransferObservation)))
    assert len(observations) == 1 and observations[0].athlete_external_id == "2"
    assert observations[0].canonical_transfer_id is observations[0].athlete_competitor_id is None
    assert await snapshot(session) == before
    session.commit.assert_not_awaited()
    await session.rollback()
    assert list(await session.scalars(select(SportsTransferObservation))) == []


@pytest.mark.parametrize(
    "state",
    [
        "missing_capability",
        "inactive_capability",
        "inactive_source",
        "missing_source",
        "missing_provider",
        "inactive_sport",
    ],
)
async def test_ineligible_discovery_never_calls_http(session, state):
    sport, source, cap = await seed(session)
    if state == "missing_capability":
        await session.delete(cap)
    elif state == "inactive_capability":
        cap.is_active = False
    elif state == "inactive_source":
        source.is_active = False
    elif state == "missing_source":
        source.slug = "other"
    elif state == "inactive_sport":
        sport.is_active = False
    await session.flush()
    registry = ProviderRegistry()
    provider = SportmonksProvider(api_key="test")
    provider.fetch_team_player_ids = AsyncMock(side_effect=AssertionError("No HTTP"))
    if state != "missing_provider":
        registry.register(provider)
    before = await snapshot(session)
    result = await SportmonksTransfersTargetDiscovery(session=session, registry=registry).discover(
        reference_date=DAY
    )
    assert result.player_ids == ()
    provider.fetch_team_player_ids.assert_not_awaited()
    assert await snapshot(session) == before


@pytest.mark.parametrize("error", [ValueError("secret"), ProviderAccessRestrictedError()])
async def test_team_failure_does_not_lose_other_targets(session, error):
    await seed(session, ("53", "62"))
    registry = ProviderRegistry()
    provider = SportmonksProvider(api_key="test")
    provider.fetch_team_player_ids = AsyncMock(side_effect=[error, ("37337109",)])
    registry.register(provider)
    result = await SportmonksTransfersTargetDiscovery(session=session, registry=registry).discover(
        reference_date=DAY
    )
    assert result.player_ids == ("37337109",)
    assert [a.success for a in result.attempts] == [False, True]
    assert "secret" not in repr(result)


async def test_discovery_sql_error_propagates(session):
    registry = ProviderRegistry()
    discovery = SportmonksTransfersTargetDiscovery(session=session, registry=registry)
    discovery.repository.get_active_source_for_capability = AsyncMock(
        side_effect=SQLAlchemyError("database failure")
    )
    with pytest.raises(SQLAlchemyError):
        await discovery.discover(reference_date=DAY)


@pytest.mark.parametrize("limit", [2, 3, 10])
async def test_team_cursor_full_coverage_and_no_writes(session, limit):
    ids = ["9", "11", "2", "21", "3", "62"]
    await seed(session, ids)
    before = await snapshot(session)
    registry = ProviderRegistry()
    provider = SportmonksProvider(api_key="test")
    provider.fetch_team_player_ids = AsyncMock(return_value=())
    registry.register(provider)
    discovery = SportmonksTransfersTargetDiscovery(
        session=session, registry=registry, max_teams=limit
    )
    cursor = None
    visited = []
    while True:
        result = await discovery.discover(reference_date=DAY, after_team_external_id=cursor)
        page = [attempt.team_external_id for attempt in result.attempts]
        assert not set(visited).intersection(page)
        visited.extend(page)
        assert result.has_more == result.teams_limited == (len(visited) < len(ids))
        if not result.has_more:
            assert result.next_cursor is None
            break
        assert result.next_cursor == page[-1]
        cursor = result.next_cursor
    assert visited == sorted(ids)
    assert provider.fetch_team_player_ids.await_count == len(ids)
    again = await discovery.discover(reference_date=DAY)
    assert [a.team_external_id for a in again.attempts] == sorted(ids)[:limit]
    assert await snapshot(session) == before


async def test_team_cursor_removed_pivot_and_insertions(session):
    sport, source, _ = await seed(session, ("1", "3", "5", "7"))
    registry = ProviderRegistry()
    provider = SportmonksProvider(api_key="test")
    provider.fetch_team_player_ids = AsyncMock(return_value=())
    registry.register(provider)
    discovery = SportmonksTransfersTargetDiscovery(session=session, registry=registry, max_teams=2)
    first = await discovery.discover(reference_date=DAY)
    assert first.next_cursor == "3"
    pivot = await session.scalar(
        select(SportsCompetitor).where(SportsCompetitor.external_id == "3")
    )
    await session.delete(pivot)
    for identity in ("2", "4"):
        await add(
            session,
            SportsCompetitor,
            source_id=source.id,
            sport_id=sport.id,
            competitor_type="team",
            name="New team",
            external_id=identity,
        )
    second = await discovery.discover(reference_date=DAY, after_team_external_id=first.next_cursor)
    assert [a.team_external_id for a in second.attempts] == ["4", "5"]
    assert second.next_cursor == "5"
    end = await discovery.discover(reference_date=DAY, after_team_external_id="9")
    assert end.attempts == () and not end.has_more and end.next_cursor is None


async def test_runtime_drains_players_before_advancing_teams(session, monkeypatch):
    from app.sms24.transfers_batch import AutomaticTransfersCursor
    from app.sms24.transfers_runner import TransfersProviderAttempt, TransfersRunnerResult

    await seed(session, ("2", "11"))
    before = await snapshot(session)
    registry = ProviderRegistry()
    provider = SportmonksProvider(api_key="test")

    async def fetch(*, team_external_id, reference_date):
        assert reference_date == DAY
        return ("3", "2", "1") if team_external_id == "11" else ("6", "5", "4")

    provider.fetch_team_player_ids = AsyncMock(side_effect=fetch)
    registry.register(provider)
    runner = AsyncMock()
    runner.run.return_value = TransfersRunnerResult([TransfersProviderAttempt("sportmonks", True)])
    monkeypatch.setattr(runtime, "build_sms24_provider_registry", lambda settings: registry)
    monkeypatch.setattr(runtime, "TransfersRunner", lambda **kwargs: runner)
    cursor = None
    continuations = []
    for _ in range(4):
        result = await runtime.run_sms24_automatic_transfers(
            session, reference_date=DAY, max_teams=1, max_players=2, cursor=cursor
        )
        cursor = result.next_cursor
        continuations.append(cursor)
    assert continuations == [
        AutomaticTransfersCursor(None, "2"),
        AutomaticTransfersCursor("11", None),
        AutomaticTransfersCursor("11", "5"),
        None,
    ]
    assert [call.kwargs["targets"] for call in runner.run.await_args_list] == [
        {"sportmonks": str(number)} for number in range(1, 7)
    ]
    assert await snapshot(session) == before


async def test_failed_team_advances_continuation(session):
    await seed(session, ("53", "62"))
    registry = ProviderRegistry()
    provider = SportmonksProvider(api_key="test")
    provider.fetch_team_player_ids = AsyncMock(side_effect=[ValueError("secret"), ()])
    registry.register(provider)
    discovery = SportmonksTransfersTargetDiscovery(session=session, registry=registry, max_teams=1)
    first = await discovery.discover(reference_date=DAY)
    assert not first.attempts[0].success and first.next_cursor == "53"
    second = await discovery.discover(reference_date=DAY, after_team_external_id=first.next_cursor)
    assert second.attempts[0].team_external_id == "62" and second.attempts[0].success
    assert second.next_cursor is None and not second.has_more
