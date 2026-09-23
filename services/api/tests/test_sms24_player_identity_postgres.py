"""Player ingestion in rollback-only disposable PostgreSQL schemas."""

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.models.sport import Sport
from app.models.sports_live import SportsCanonicalCompetitor, SportsCompetitor, SportsDataSource
from app.sms24.player_identity_discovery import PlayerIdentityDiscovery, PlayerIdentityTeamTarget
from app.sms24.providers.player_identity import ProviderPlayerIdentity
from app.sms24.providers.registry import ProviderRegistry
from tests import test_sms24_player_statistics_postgres as foundation
from tests.test_sms24_transfers_postgres import NOW, add

previous_connection = foundation.previous_connection
connection = foundation.connection
session = foundation.session
DAY = date(2026, 9, 22)


@pytest.fixture(autouse=True)
def no_http(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("No real HTTP allowed")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)


async def setup(session, *, slug="sportmonks", sport=None, external_id="62", ids=("758",)):
    sport = sport or await add(session, Sport, slug="football", name="Football")
    source = await add(session, SportsDataSource, slug=slug, name=slug)
    team = await add(
        session,
        SportsCompetitor,
        source_id=source.id,
        sport_id=sport.id,
        external_id=external_id,
        name="Known team",
        competitor_type="team",
    )
    provider = SimpleNamespace(
        slug=slug,
        fetch_team_player_ids=AsyncMock(return_value=ids),
        fetch_player_identity=AsyncMock(
            side_effect=lambda **kw: ProviderPlayerIdentity(
                external_id=kw["athlete_external_id"],
                name="Same Official Name",
                fetched_at=NOW,
            )
        ),
    )
    registry = ProviderRegistry()
    registry.register(provider)
    service = PlayerIdentityDiscovery(session=session, registry=registry)
    return sport, source, team, provider, service


async def run(service, team, slug="sportmonks"):
    return await service.run(targets=(PlayerIdentityTeamTarget(slug, team.id),), reference_date=DAY)


async def athletes(session):
    return list(
        (
            await session.scalars(
                select(SportsCompetitor)
                .where(
                    SportsCompetitor.competitor_type == "athlete",
                )
                .order_by(SportsCompetitor.external_id)
            )
        ).all()
    )


async def untouched(session):
    tables = (
        "users",
        "profiles",
        "athletes",
        "athlete_performances",
        "sports_athlete_identity_links",
        "sports_data_sources",
        "sports_data_source_capabilities",
        "sports_player_statistic_observations",
    )
    return {
        table: (await session.execute(text(f'SELECT * FROM "{table}" ORDER BY 1'))).all()
        for table in tables
    }


async def test_ingestion_dedup_replay_rename_provider_scope_and_no_human_writes(session):
    sport, source, team, provider, service = await setup(session, ids=("758", "759", "758"))
    before = await untouched(session)
    first = await run(service, team)
    assert (first.teams_processed, first.players_discovered, first.players_processed) == (1, 2, 2)
    assert first.failures == []
    provider.fetch_team_player_ids.assert_awaited_once_with(
        team_external_id="62", reference_date=DAY
    )
    assert provider.fetch_player_identity.await_count == 2
    rows = await athletes(session)
    original = {row.external_id: (row.id, row.canonical_competitor_id) for row in rows}
    assert len(rows) == 2
    assert len({row.canonical_competitor_id for row in rows}) == 2
    for row in rows:
        assert row.source_id == source.id and row.sport_id == sport.id
        assert row.country_code is None
        canonical = await session.get(SportsCanonicalCompetitor, row.canonical_competitor_id)
        assert canonical.identity_scope == "provider_scoped" and canonical.country_code is None
    provider.fetch_player_identity.side_effect = lambda **kw: ProviderPlayerIdentity(
        external_id=kw["athlete_external_id"],
        name="Changed Official Name",
        fetched_at=NOW,
    )
    assert (await run(service, team)).players_processed == 2
    rows = await athletes(session)
    assert {row.external_id: (row.id, row.canonical_competitor_id) for row in rows} == original
    assert all(row.name == "Changed Official Name" for row in rows)
    assert await untouched(session) == before


async def test_same_name_across_providers_stays_distinct(session):
    sport, _, team, _, service = await setup(session)
    _, _, other, _, other_service = await setup(session, slug="other", sport=sport)
    await run(service, team)
    await run(other_service, other, "other")
    rows = await athletes(session)
    assert len(rows) == 2
    assert len({row.canonical_competitor_id for row in rows}) == 2


@pytest.mark.parametrize(
    "invalid",
    [
        "missing",
        "athlete",
        "sport",
        "source",
        "slug",
        "unregistered",
        "unsupported",
        "provider_slug",
    ],
)
async def test_target_invalid_before_any_provider_call(session, invalid):
    sport, source, team, provider, service = await setup(session)
    if invalid == "missing":
        team = SimpleNamespace(id=uuid.uuid4())
    elif invalid == "athlete":
        team.competitor_type = "athlete"
    elif invalid == "sport":
        sport.is_active = False
    elif invalid == "source":
        source.is_active = False
    elif invalid == "unregistered":
        service.registry.clear()
    elif invalid == "unsupported":
        provider.fetch_player_identity = None
    elif invalid == "provider_slug":
        provider.slug = "other"
    with pytest.raises(ValueError):
        await run(service, team, "other" if invalid == "slug" else "sportmonks")
    provider.fetch_team_player_ids.assert_not_awaited()
    assert await athletes(session) == ([team] if invalid == "athlete" else [])


@pytest.mark.parametrize("failure", ["mismatch", "name", "provider", "ingestion"])
async def test_local_failure_and_savepoint_leave_other_player_valid(session, failure):
    _, _, team, provider, service = await setup(session, ids=("1", "2"))
    original = service.repository.upsert_competitor

    async def upsert(**kw):
        row = await original(**kw)
        if kw["participant"].external_id == "1" and failure == "ingestion":
            raise ValueError("secret")
        return row

    service.repository.upsert_competitor = upsert

    async def identity(*, athlete_external_id):
        if athlete_external_id == "1":
            if failure == "provider":
                raise RuntimeError("secret token URL body")
            if failure == "name":
                return ProviderPlayerIdentity(external_id="1", name="", fetched_at=NOW)
            if failure == "mismatch":
                return ProviderPlayerIdentity(external_id="3", name="Official", fetched_at=NOW)
        return ProviderPlayerIdentity(
            external_id=athlete_external_id, name="Official", fetched_at=NOW
        )

    provider.fetch_player_identity.side_effect = identity
    result = await run(service, team)
    assert result.players_discovered == 2 and result.players_processed == 1
    assert len(result.failures) == 1 and result.failures[0].player_external_id == "1"
    assert "secret" not in repr(result)
    assert [row.external_id for row in await athletes(session)] == ["2"]
    assert len((await session.scalars(select(SportsCanonicalCompetitor))).all()) == 1


@pytest.mark.parametrize("stage", ["team", "player", "ingestion"])
async def test_sql_errors_propagate(session, stage):
    _, _, team, provider, service = await setup(session)
    if stage == "team":
        provider.fetch_team_player_ids.side_effect = SQLAlchemyError("database")
    elif stage == "player":
        provider.fetch_player_identity.side_effect = SQLAlchemyError("database")
    else:
        service.repository.upsert_competitor = AsyncMock(side_effect=SQLAlchemyError("database"))
    with pytest.raises(SQLAlchemyError):
        await run(service, team)


async def test_multiple_teams_deduplicate_player_before_identity_fetch(session):
    sport, source, team, provider, service = await setup(session)
    other = await add(
        session,
        SportsCompetitor,
        source_id=source.id,
        sport_id=sport.id,
        external_id="53",
        name="Other team",
        competitor_type="team",
    )
    result = await service.run(
        targets=tuple(PlayerIdentityTeamTarget("sportmonks", t.id) for t in (team, other, team)),
        reference_date=DAY,
    )
    assert (result.teams_processed, result.players_discovered, result.players_processed) == (
        2,
        1,
        1,
    )
    assert provider.fetch_player_identity.await_count == 1


async def test_source_id_collision_with_team_is_rejected(session):
    _, _, team, _, service = await setup(session, ids=("62",))
    result = await run(service, team)
    assert result.players_processed == 0
    assert result.failures[0].reason == "ingestion_validation_failed"
    assert team.competitor_type == "team"


async def test_existing_canonical_resolution_is_not_replaced(session):
    sport, source, team, _, service = await setup(session)
    canonical = await add(
        session,
        SportsCanonicalCompetitor,
        sport_id=sport.id,
        canonical_key="explicit",
        identity_scope="verified_context",
        competitor_type="athlete",
        name="Official",
        normalized_name="official",
    )
    player = await add(
        session,
        SportsCompetitor,
        source_id=source.id,
        sport_id=sport.id,
        external_id="758",
        name="Official",
        competitor_type="athlete",
        canonical_competitor_id=canonical.id,
    )
    result = await run(service, team)
    assert result.players_processed == 0
    assert player.canonical_competitor_id == canonical.id


async def test_caller_rollback_removes_player_and_canonical(session):
    _, _, team, _, service = await setup(session)
    transaction = await session.begin_nested()
    assert (await run(service, team)).players_processed == 1
    await transaction.rollback()
    assert await athletes(session) == []
    assert (await session.scalars(select(SportsCanonicalCompetitor))).all() == []


@pytest.mark.parametrize("ids", [(), [], (None,), (True,), (" ",)])
async def test_empty_or_malformed_team_player_result(session, ids):
    _, _, team, provider, service = await setup(session, ids=ids)
    result = await run(service, team)
    assert result.players_processed == 0
    assert bool(result.failures) == (ids != ())
    provider.fetch_player_identity.assert_not_awaited()


async def test_all_targets_are_validated_before_network(session):
    _, _, team, provider, service = await setup(session)
    with pytest.raises(ValueError):
        await service.run(
            targets=(
                PlayerIdentityTeamTarget("sportmonks", team.id),
                PlayerIdentityTeamTarget("sportmonks", uuid.uuid4()),
            ),
            reference_date=DAY,
        )
    provider.fetch_team_player_ids.assert_not_awaited()


async def test_failed_team_does_not_block_next_team(session):
    sport, source, team, provider, service = await setup(session)
    other = await add(
        session,
        SportsCompetitor,
        source_id=source.id,
        sport_id=sport.id,
        external_id="53",
        name="Other",
        competitor_type="team",
    )
    provider.fetch_team_player_ids.side_effect = [RuntimeError("private-token"), ("758",)]
    result = await service.run(
        targets=tuple(PlayerIdentityTeamTarget("sportmonks", t.id) for t in (team, other)),
        reference_date=DAY,
    )
    assert result.teams_processed == 1 and result.players_processed == 1
    assert result.failures[0].reason == "team_discovery_failed"
    assert "private-token" not in repr(result)


async def test_sport_conflict_preserves_existing_player(session):
    _, source, team, _, service = await setup(session)
    sport = await add(session, Sport, slug="tennis", name="Tennis")
    player = await add(
        session,
        SportsCompetitor,
        source_id=source.id,
        sport_id=sport.id,
        external_id="758",
        name="Existing",
        competitor_type="athlete",
    )
    result = await run(service, team)
    assert result.players_processed == 0 and len(result.failures) == 1
    assert player.sport_id == sport.id and player.name == "Existing"


async def test_real_adapter_composition_with_mock_http(session):
    from app.sms24.providers.sportmonks import SportmonksProvider

    _, _, team, _, service = await setup(session)
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/teams/62"):
            assert request.url.params["include"] == "players"
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": 62,
                        "players": [
                            {"team_id": 62, "player_id": 758, "start": None, "end": None},
                        ],
                    }
                },
            )
        assert not request.url.params
        return httpx.Response(200, json={"data": {"id": 758, "name": "James Tavernier"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service.registry.clear()
        service.registry.register(SportmonksProvider(api_key="test", client=client))
        result = await run(service, team)
    assert result.players_processed == 1
    assert paths == ["/v3/football/teams/62", "/v3/football/players/758"]
    assert (await athletes(session))[0].name == "James Tavernier"


@pytest.mark.parametrize("stage", ["team", "player"])
async def test_access_restricted_is_local_and_sanitized(session, stage):
    from app.sms24.providers.errors import ProviderAccessRestrictedError

    _, _, team, provider, service = await setup(session)
    method = provider.fetch_team_player_ids if stage == "team" else provider.fetch_player_identity
    method.side_effect = ProviderAccessRestrictedError()
    result = await run(service, team)
    assert result.players_processed == 0
    assert result.failures[0].reason == "provider_access_restricted"
    assert await athletes(session) == []


async def test_unexpected_persistence_error_is_not_hidden(session):
    _, _, team, _, service = await setup(session)
    service.repository.upsert_competitor = AsyncMock(side_effect=RuntimeError("unexpected"))
    with pytest.raises(RuntimeError, match="unexpected"):
        await run(service, team)
