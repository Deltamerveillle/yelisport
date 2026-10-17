"""0037 and local observations, using only the opt-in disposable PostgreSQL fixture."""

import importlib
import uuid
from dataclasses import replace
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import insert, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_performance import AthletePerformance
from app.models.sports_live import (
    SportsCanonicalCompetition,
    SportsCanonicalFixture,
    SportsCompetition,
    SportsCompetitor,
    SportsFixture,
    SportsSeason,
)
from app.models.sports_player_statistics import SportsPlayerStatisticObservation as Observation
from app.models.user import Profile
from app.sms24.player_statistics import SMS24PlayerStatisticsRepository
from app.sms24.providers.player_statistics import ProviderPlayerStatistic
from tests import test_sms24_transfers_postgres as foundation
from tests.test_sms24_transfers_postgres import NOW, add, count

M35 = importlib.import_module(
    "app.db.migrations.versions.20260920_0035_enable_sportmonks_transfers"
)
M36 = importlib.import_module("app.db.migrations.versions.20260920_0036_add_sms24_job_checkpoints")
M37 = importlib.import_module(
    "app.db.migrations.versions.20260921_0037_add_sms24_player_statistics_foundation",
)
previous_connection = foundation.connection


@pytest.fixture(autouse=True)
def no_http(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No real HTTP in the statistics foundation")

    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)
    monkeypatch.setattr(httpx.Client, "send", forbidden)


@pytest.fixture
async def connection(previous_connection):
    await previous_connection.run_sync(
        lambda sync: foundation.Base.metadata.create_all(
            sync,
            tables=[
                model.__table__
                for model in (
                    Profile,
                    AthletePerformance,
                    SportsCanonicalFixture,
                    SportsCompetition,
                    SportsFixture,
                )
            ],
        )
    )
    for migration in (foundation.M34, M35, M36):
        await previous_connection.run_sync(lambda sync, m=migration: foundation.migrate(sync, m))
    yield previous_connection


@pytest.fixture
async def session(connection):
    await connection.run_sync(lambda sync: foundation.migrate(sync, M37))
    async with AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as session:
        yield session


async def setup(session):
    sport = await add(session, foundation.Sport, slug="athletics", name="Athletics")
    source = await add(session, foundation.SportsDataSource, slug="stats-one", name="Stats")
    return sport, source, SMS24PlayerStatisticsRepository(session)


def payload(**changes):
    return ProviderPlayerStatistic(
        **{
            "athlete_external_id": "p1",
            "external_id": "record-1",
            "fixture_external_id": "fixture-1",
            **changes,
        }
    )


async def record(repo, sport, source, statistic=None, fetched_at=NOW):
    return await repo.record_observation(
        source_id=source.id,
        sport_id=sport.id,
        statistic=statistic or payload(),
        fetched_at=fetched_at,
    )


async def graph(session, sport, source):
    canonical_competition = await add(
        session,
        SportsCanonicalCompetition,
        sport_id=sport.id,
        canonical_key=str(uuid.uuid4()),
        name="Cup",
        normalized_name="cup",
    )
    competition = await add(
        session,
        SportsCompetition,
        source_id=source.id,
        sport_id=sport.id,
        external_id=str(uuid.uuid4()),
        name="Cup",
        canonical_competition_id=canonical_competition.id,
    )
    season = await add(
        session,
        SportsSeason,
        canonical_competition_id=canonical_competition.id,
        label="2026",
        normalized_label="2026",
    )
    canonical = await add(
        session,
        SportsCanonicalFixture,
        sport_id=sport.id,
        canonical_key=str(uuid.uuid4()),
        participant_signature="explicit",
        starts_at=NOW,
    )
    fixture = await add(
        session,
        SportsFixture,
        sport_id=sport.id,
        source_id=source.id,
        competition_id=competition.id,
        external_id="fixture-1",
        starts_at=NOW,
        canonical_fixture_id=canonical.id,
    )
    athlete = await add(
        session,
        SportsCompetitor,
        sport_id=sport.id,
        source_id=source.id,
        external_id="p1",
        name="Provider name",
        competitor_type="athlete",
    )
    return athlete, fixture, canonical, season, competition


async def test_migration_roundtrip_and_model_match(connection):
    assert M37.down_revision == M36.revision
    before = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
    protected = {}
    for name in before:
        table = foundation.Base.metadata.tables[name]
        protected[name] = (await connection.execute(select(table))).mappings().all()
    for direction in ("upgrade", "downgrade", "upgrade"):
        await connection.run_sync(lambda sync, d=direction: foundation.migrate(sync, M37, d))
        tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
        assert set(tables) == set(before) | (
            {Observation.__tablename__} if direction == "upgrade" else set()
        )
        for name, rows in protected.items():
            assert (
                await connection.execute(select(foundation.Base.metadata.tables[name]))
            ).mappings().all() == rows

    def check(sync):
        db = inspect(sync)
        table = Observation.__table__
        actual = db.get_columns(table.name)
        assert {c["name"]: c["nullable"] for c in actual} == {c.name: c.nullable for c in table.c}
        assert {c["name"] for c in db.get_check_constraints(table.name)} == {
            c.name for c in table.constraints if c.__class__.__name__ == "CheckConstraint"
        }
        assert {
            i["name"] for i in db.get_indexes(table.name) if not i.get("duplicates_constraint")
        } == {i.name for i in table.indexes}
        assert all(
            fk["options"]["ondelete"] == "RESTRICT" for fk in db.get_foreign_keys(table.name)
        )

    await connection.run_sync(check)


@pytest.mark.parametrize(
    "changes",
    [
        {"sport_id": None},
        {"sport_id": uuid.uuid4()},
        {"source_id": uuid.uuid4()},
        {"athlete_external_id": " "},
        {"observation_key": ""},
        {"external_id": None},
        {"external_id": ""},
        {"scope": "verified"},
        {"metrics_json": []},
        {"metrics_json": None},
        {"metadata_json": [1]},
        {"metadata_json": None},
        {"fetched_at": None},
        {"fixture_id": uuid.uuid4()},
        {"athlete_competitor_id": uuid.uuid4()},
        {"canonical_fixture_id": uuid.uuid4()},
        {"season_id": uuid.uuid4()},
        {"fixture_external_id": ""},
        {"record_reference": " "},
    ],
)
async def test_database_constraints(session, changes):
    sport, source, _ = await setup(session)
    with pytest.raises(IntegrityError), session.no_autoflush:
        async with session.begin_nested():
            await session.execute(
                insert(Observation).values(
                    **{
                        "sport_id": sport.id,
                        "source_id": source.id,
                        "observation_key": "opaque-key",
                        "athlete_external_id": "p",
                        "external_id": "r",
                        "fetched_at": NOW,
                        **changes,
                    }
                )
            )


@pytest.mark.parametrize("reference_only", [False, True])
async def test_idempotence_source_separation_stale_equal_and_protected_data(
    session, reference_only
):
    sport, source, repo = await setup(session)
    person = await foundation.human(session, sport)
    await add(session, Profile, user_id=person.user_id, display_name="Owner")
    await add(
        session,
        AthletePerformance,
        athlete_id=person.id,
        sport_id=sport.id,
        performance_date=NOW.date(),
        metrics={"time_seconds": 10.5},
        verification_status="declared",
    )
    protected = (
        foundation.User,
        Profile,
        foundation.Athlete,
        AthletePerformance,
        foundation.SportsAthleteIdentityLink,
        foundation.SportsCanonicalTransfer,
        foundation.SportsDataSource,
        foundation.SportsDataSourceCapability,
    )
    before = {m: (await session.execute(select(m.__table__))).mappings().all() for m in protected}
    data = payload(
        external_id=None if reference_only else "r",
        record_reference="opaque-reference" if reference_only else None,
        metrics={"time_seconds": None, "points": 0},
    )
    first = await record(repo, sport, source, data)
    identity = first.id
    assert (await record(repo, sport, source, data)).id == identity
    assert await count(session, Observation) == 1
    fresh = replace(
        data, metrics={"distance": 100, "time_seconds": 10.1}, metadata={"reported": True}
    )
    await record(repo, sport, source, fresh, NOW + timedelta(days=1))
    stale = await record(repo, sport, source, data)
    assert stale.metrics_json == fresh.metrics
    equal = await record(repo, sport, source, data, NOW + timedelta(days=1))
    assert equal.metrics_json == {"time_seconds": None, "points": 0}
    assert "distance" not in equal.metrics_json
    assert equal.athlete_competitor_id is None
    for m, rows in before.items():
        assert (await session.execute(select(m.__table__))).mappings().all() == rows
    assert await count(session, SportsCompetitor) == 0
    other_source = await add(session, foundation.SportsDataSource, slug="stats-two", name="Stats")
    assert (await record(repo, sport, other_source, data)).id != identity


@pytest.mark.parametrize("change", ["athlete", "sport"])
async def test_identity_cannot_change_even_for_stale_snapshot(session, change):
    sport, source, repo = await setup(session)
    await record(repo, sport, source)
    other = await add(session, foundation.Sport, slug="rugby", name="Rugby")
    with pytest.raises(ValueError, match="cannot change"):
        await record(
            repo,
            other if change == "sport" else sport,
            source,
            payload(athlete_external_id="other" if change == "athlete" else "p1"),
            NOW - timedelta(days=1),
        )


async def test_resolution_preserved_by_ingestion_and_omission(session):
    sport, source, repo = await setup(session)
    athlete, fixture, canonical, season, _ = await graph(session, sport, source)
    observation = await record(repo, sport, source)
    ids = dict(
        observation_id=observation.id,
        athlete_competitor_id=athlete.id,
        fixture_id=fixture.id,
        canonical_fixture_id=canonical.id,
        season_id=season.id,
    )
    linked = await repo.resolve_observation(**ids)
    assert linked.fixture_id == fixture.id
    assert linked.canonical_fixture_id == canonical.id
    assert linked.season_id == season.id
    await record(repo, sport, source, payload(metrics={"points": 0}))
    again = await repo.resolve_observation(
        observation_id=ids["observation_id"], athlete_competitor_id=athlete.id
    )
    assert again.season_id == season.id and again.canonical_fixture_id == canonical.id
    with pytest.raises(ValueError, match="fixture must match"):
        await record(repo, sport, source, payload(fixture_external_id="wrong"))
    for key in ("athlete_competitor_id", "fixture_id", "canonical_fixture_id", "season_id"):
        with pytest.raises(ValueError, match="reconciliation"):
            await repo.resolve_observation(**{**ids, key: uuid.uuid4()})
    for model in (
        foundation.User,
        Profile,
        foundation.Athlete,
        AthletePerformance,
        foundation.SportsAthleteIdentityLink,
    ):
        assert await count(session, model) == 0


@pytest.mark.parametrize(
    "invalid",
    [
        "athlete_source",
        "athlete_external",
        "athlete_type",
        "athlete_sport",
        "canonical_athlete",
        "fixture_source",
        "fixture_external",
        "fixture_sport",
        "canonical_fixture",
        "canonical_sport",
        "season_sport",
        "season_competition",
        "competition_source",
        "competition_sport",
        "unmapped_competition",
    ],
)
async def test_resolution_rejects_graph_incoherence(session, invalid):
    sport, source, repo = await setup(session)
    athlete, fixture, canonical, season, competition = await graph(session, sport, source)
    other = await add(session, foundation.Sport, slug="rugby", name="Rugby")
    other_source = await add(session, foundation.SportsDataSource, slug="other", name="Other")
    if invalid.startswith("athlete_"):
        field = {
            "athlete_source": "source_id",
            "athlete_external": "external_id",
            "athlete_type": "competitor_type",
            "athlete_sport": "sport_id",
        }[invalid]
        setattr(
            athlete,
            field,
            {
                "source_id": other_source.id,
                "external_id": "other",
                "competitor_type": "team",
                "sport_id": other.id,
            }[field],
        )
    elif invalid == "canonical_athlete":
        node = await foundation.canonical(session, other)
        athlete.canonical_competitor_id = node.id
    elif invalid.startswith("fixture_"):
        field = {
            "fixture_source": "source_id",
            "fixture_external": "external_id",
            "fixture_sport": "sport_id",
        }[invalid]
        setattr(
            fixture,
            field,
            {"source_id": other_source.id, "external_id": "other", "sport_id": other.id}[field],
        )
    elif invalid == "canonical_fixture":
        fixture.canonical_fixture_id = None
    elif invalid == "canonical_sport":
        canonical.sport_id = other.id
    elif invalid.startswith("season_"):
        node = await add(
            session,
            SportsCanonicalCompetition,
            sport_id=other.id if invalid == "season_sport" else sport.id,
            canonical_key="other",
            name="Other",
            normalized_name="other",
        )
        season.canonical_competition_id = node.id
    elif invalid == "competition_source":
        competition.source_id = other_source.id
    elif invalid == "competition_sport":
        competition.sport_id = other.id
    elif invalid == "unmapped_competition":
        competition.canonical_competition_id = None
    await session.flush()
    observation = await record(repo, sport, source)
    with pytest.raises(ValueError):
        await repo.resolve_observation(
            observation_id=observation.id,
            athlete_competitor_id=athlete.id,
            fixture_id=fixture.id,
            canonical_fixture_id=canonical.id,
            season_id=season.id,
        )


async def test_resolution_requires_reported_fixture_identity_and_explicit_path(session):
    sport, source, repo = await setup(session)
    athlete, fixture, canonical, _, _ = await graph(session, sport, source)
    row = await record(repo, sport, source, payload(fixture_external_id=None))
    ids = dict(observation_id=row.id, athlete_competitor_id=athlete.id)
    with pytest.raises(ValueError, match="reported provider"):
        await repo.resolve_observation(**ids, fixture_id=fixture.id)
    with pytest.raises(ValueError, match="explicit provider fixture"):
        await repo.resolve_observation(**ids, canonical_fixture_id=canonical.id)


async def test_rollback_discards_observation(session):
    sport, source, repo = await setup(session)
    with pytest.raises(RuntimeError):
        async with session.begin_nested():
            await record(repo, sport, source)
            raise RuntimeError("Caller rollback")
    assert await count(session, Observation) == 0


async def test_database_identity_uniqueness_and_nullable_external_id(session):
    sport, source, repo = await setup(session)
    row = await record(repo, sport, source)
    key = row.observation_key
    base = dict(source_id=source.id, sport_id=sport.id, athlete_external_id="p1", fetched_at=NOW)
    for changes in (
        {"observation_key": "another-key", "external_id": "record-1"},
        {"observation_key": key, "external_id": "another-external-id"},
    ):
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.execute(insert(Observation).values(**base, **changes))
    for reference in ("opaque-a", "opaque-b"):
        await repo.record_observation(
            source_id=base["source_id"],
            sport_id=base["sport_id"],
            fetched_at=NOW,
            statistic=payload(external_id=None, record_reference=reference),
        )
    assert await count(session, Observation) == 3
