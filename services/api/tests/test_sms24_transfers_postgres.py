"""0034 DDL and local domain tests in disposable, rollback-only PostgreSQL schemas.

An explicit SMS24_MIGRATION_TEST_DATABASE_URL is required. No app DB URL, provider
settings, network fetching, or real database migrations are used here.
"""

import importlib
import os
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, insert, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.models.athlete import Athlete
from app.models.athlete_country_eligibility import AthleteCountryEligibility
from app.models.athlete_passport import AthletePassport
from app.models.country import Country
from app.models.sport import Sport
from app.models.sports_live import (
    SportsCanonicalCompetition,
    SportsCanonicalCompetitor,
    SportsCompetitor,
    SportsDataSource,
    SportsDataSourceCapability,
    SportsSeason,
)
from app.models.sports_transfers import (
    SportsAthleteIdentityLink,
    SportsCanonicalTransfer,
    SportsTransferObservation,
)
from app.models.user import User
from app.sms24.ingestion import SMS24IngestionRepository
from app.sms24.providers import ProviderParticipant
from app.sms24.providers.transfers import ProviderTransfer
from app.sms24.transfers import SMS24TransfersRepository

M32 = importlib.import_module(
    "app.db.migrations.versions.20260912_0032_add_sms24_source_capabilities"
)
M33 = importlib.import_module("app.db.migrations.versions.20260913_0033_seed_gnews_news_source")
M34 = importlib.import_module(
    "app.db.migrations.versions.20260916_0034_add_sms24_transfers_foundation"
)
NEW_MODELS = (SportsAthleteIdentityLink, SportsCanonicalTransfer, SportsTransferObservation)
NOW = datetime(2026, 9, 16, tzinfo=UTC)


def migrate(connection, migration, direction="upgrade"):
    with Operations.context(MigrationContext.configure(connection)):
        getattr(migration, direction)()


@pytest.fixture
async def connection():
    url = os.environ.get("SMS24_MIGRATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set SMS24_MIGRATION_TEST_DATABASE_URL to a disposable PostgreSQL DB")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                schema = f"sms24_0034_test_{uuid.uuid4().hex}"
                await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                await conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                await conn.run_sync(
                    lambda sync: Base.metadata.create_all(
                        sync,
                        tables=[
                            model.__table__
                            for model in (
                                Sport,
                                Country,
                                User,
                                Athlete,
                                AthletePassport,
                                AthleteCountryEligibility,
                                SportsDataSource,
                                SportsCanonicalCompetition,
                                SportsCanonicalCompetitor,
                                SportsSeason,
                                SportsCompetitor,
                            )
                        ],
                    )
                )
                await conn.run_sync(lambda sync: migrate(sync, M32))
                await conn.run_sync(lambda sync: migrate(sync, M33))
                yield conn
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
async def session(connection):
    await connection.run_sync(lambda sync: migrate(sync, M34))
    async with AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as session:
        yield session


async def add(session, model, **values):
    row = model(**values)
    session.add(row)
    await session.flush()
    return row


async def count(session, model):
    return await session.scalar(select(func.count()).select_from(model))


async def seed(session):
    sport = await add(session, Sport, slug="football", name="Football")
    sources = [
        await add(session, SportsDataSource, slug=f"provider-{i}", name="Provider")
        for i in range(2)
    ]
    athlete = await canonical(session, sport)
    return sport, sources, athlete


async def canonical(session, sport, kind="athlete"):
    return await add(
        session,
        SportsCanonicalCompetitor,
        sport_id=sport.id,
        competitor_type=kind,
        canonical_key=f"explicit:{uuid.uuid4()}",
        name="Same Name",
        normalized_name="same name",
        identity_scope="provider_scoped",
    )


async def human(session, sport):
    user = await add(session, User, id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.test")
    return await add(
        session, Athlete, user_id=user.id, sport_id=sport.id, first_name="Same", last_name="Name"
    )


async def test_migration_round_trip_preserves_0033_and_matches_models(connection):
    assert M34.down_revision == M33.revision
    before = (await connection.execute(select(SportsDataSource.__table__))).mappings().all()
    caps = (await connection.execute(select(SportsDataSourceCapability.__table__))).mappings().all()
    for _ in range(2):
        await connection.run_sync(lambda sync: migrate(sync, M34))

        def check(sync):
            db = inspect(sync)
            for model in NEW_MODELS:
                table = model.__table__
                columns = {c["name"]: c for c in db.get_columns(table.name)}
                assert set(columns) == set(table.c.keys())
                for column in table.c:
                    assert columns[column.name]["nullable"] == column.nullable
                assert {i["name"] for i in db.get_indexes(table.name)} >= {
                    i.name for i in table.indexes
                }
                assert {c["name"] for c in db.get_check_constraints(table.name)} == {
                    c.name for c in table.constraints if c.__class__.__name__ == "CheckConstraint"
                }

        await connection.run_sync(check)
        await connection.run_sync(lambda sync: migrate(sync, M34, "downgrade"))
        assert (
            await connection.execute(select(SportsDataSource.__table__))
        ).mappings().all() == before
        assert (
            await connection.execute(select(SportsDataSourceCapability.__table__))
        ).mappings().all() == caps
        names = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
        assert all(model.__tablename__ not in names for model in NEW_MODELS)


async def test_explicit_link_type_sport_uniqueness_and_history(session):
    sport, _, node = await seed(session)
    person = await human(session, sport)
    other_person = await human(session, sport)
    other_node = await canonical(session, sport)
    team = await canonical(session, sport, "team")
    other_sport = await add(session, Sport, slug="rugby", name="Rugby")
    foreign_node = await canonical(session, other_sport)
    repo = SMS24TransfersRepository(session)
    values = dict(
        athlete_id=person.id,
        method="athlete_claim",
        established_by="test-reviewer",
        evidence_reference="explicit-claim:1",
    )
    for invalid in (team, foreign_node):
        with pytest.raises(ValueError):
            await repo.link_athlete(**values, canonical_competitor_id=invalid.id)
    link = await repo.link_athlete(**values, canonical_competitor_id=node.id)
    assert link.status == "declared" and link.verified_at is None
    link_id = link.id
    # Same pair, different node, or different human cannot create duplicate active identities.
    for human_id, node_id in (
        (person.id, node.id),
        (person.id, other_node.id),
        (other_person.id, node.id),
    ):
        with pytest.raises(IntegrityError):
            await repo.link_athlete(
                **{**values, "athlete_id": human_id}, canonical_competitor_id=node_id
            )
    await session.execute(
        SportsAthleteIdentityLink.__table__.update()
        .where(SportsAthleteIdentityLink.id == link_id)
        .values(ended_at=func.now())
    )
    new = await repo.link_athlete(**values, canonical_competitor_id=other_node.id)
    assert new.id != link_id
    assert await count(session, SportsAthleteIdentityLink) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "verified"},
        {"method": "provider"},
        {"evidence_reference": " "},
        {"established_by": " "},
        {"status": "trusted"},
    ],
)
async def test_identity_link_rejects_unsubstantiated_trust(session, changes):
    sport, _, node = await seed(session)
    person = await human(session, sport)
    with pytest.raises(IntegrityError):
        await SMS24TransfersRepository(session).link_athlete(
            **{
                "athlete_id": person.id,
                "canonical_competitor_id": node.id,
                "method": "athlete_claim",
                "established_by": "reviewer",
                "evidence_reference": "claim:1",
                **changes,
            }
        )
    assert await count(session, SportsAthleteIdentityLink) == 0


async def test_external_athlete_unknown_transfer_and_no_implicit_humans(session):
    _, sources, node = await seed(session)
    repo = SMS24TransfersRepository(session)
    event = await repo.create_event(canonical_athlete_id=node.id)
    assert event.movement_type == event.status == "unknown"
    assert all(
        getattr(event, name) is None
        for name in (
            "from_club_id",
            "to_club_id",
            "movement_date",
            "season_id",
            "display_type",
            "fee_amount",
            "fee_currency",
        )
    )
    observation = await repo.record_observation(
        source_id=sources[0].id,
        fetched_at=NOW,
        transfer=ProviderTransfer(athlete_external_id="player-1", external_id="e1"),
    )
    assert observation.canonical_transfer_id is None
    assert observation.athlete_competitor_id is None
    assert observation.reported_date is None and observation.reported_type is None
    for model in (
        Athlete,
        User,
        AthletePassport,
        AthleteCountryEligibility,
        SportsAthleteIdentityLink,
    ):
        assert await count(session, model) == 0


@pytest.mark.parametrize("with_id", [True, False])
async def test_observation_idempotence_source_separation_and_no_profile_mutation(session, with_id):
    sport, sources, _ = await seed(session)
    person = await human(session, sport)
    await add(session, AthletePassport, athlete_id=person.id, club_name="Owner's club")
    protected = (Athlete, User, AthletePassport, AthleteCountryEligibility)
    before = {m: (await session.execute(select(m.__table__))).mappings().all() for m in protected}
    repo = SMS24TransfersRepository(session)
    transfer = ProviderTransfer(
        athlete_external_id="player-1",
        athlete_name="Same Name",
        external_id="event-1" if with_id else None,
        record_reference=None if with_id else "stable-record-1",
        metadata={"fee": None},
    )
    first = await repo.record_observation(
        source_id=sources[0].id, transfer=transfer, fetched_at=NOW
    )
    first_id = first.id
    second = await repo.record_observation(
        source_id=sources[0].id, transfer=transfer, fetched_at=NOW
    )
    assert first_id == second.id
    other = await repo.record_observation(
        source_id=sources[1].id, transfer=transfer, fetched_at=NOW
    )
    assert other.id != first_id
    assert other.canonical_transfer_id is None and second.canonical_transfer_id is None
    assert await count(session, SportsCanonicalTransfer) == 0
    assert await count(session, SportsAthleteIdentityLink) == 0
    assert await count(session, SportsTransferObservation) == 2
    updated = await repo.record_observation(
        source_id=sources[0].id,
        fetched_at=NOW + timedelta(days=1),
        transfer=replace(transfer, reported_type="Unknown provider code", to_team_name="New club"),
    )
    stale = await repo.record_observation(
        source_id=sources[0].id, fetched_at=NOW, transfer=transfer
    )
    assert stale.reported_type == updated.reported_type == "Unknown provider code"
    with pytest.raises(ValueError):
        await repo.record_observation(
            source_id=sources[0].id,
            fetched_at=NOW + timedelta(days=2),
            transfer=replace(transfer, athlete_external_id="other-player"),
        )
    after = {m: (await session.execute(select(m.__table__))).mappings().all() for m in protected}
    assert before == after


async def test_explicit_resolution_checks_provider_identity_and_canonical_athlete(session):
    sport, sources, node = await seed(session)
    repo = SMS24TransfersRepository(session)
    event = await repo.create_event(canonical_athlete_id=node.id)
    observation = await repo.record_observation(
        source_id=sources[0].id,
        fetched_at=NOW,
        transfer=ProviderTransfer(athlete_external_id="p1", external_id="event"),
    )
    defaults = dict(
        sport_id=sport.id,
        competitor_type="athlete",
        name="Same Name",
        canonical_competitor_id=node.id,
    )
    valid = await add(
        session, SportsCompetitor, source_id=sources[0].id, external_id="p1", **defaults
    )
    wrong_source = await add(
        session, SportsCompetitor, source_id=sources[1].id, external_id="p1", **defaults
    )
    wrong_player = await add(
        session, SportsCompetitor, source_id=sources[0].id, external_id="p2", **defaults
    )
    for invalid in (wrong_source, wrong_player):
        with pytest.raises(ValueError):
            await repo.resolve_observation(
                observation_id=observation.id,
                athlete_competitor_id=invalid.id,
                canonical_transfer_id=event.id,
            )
    other_node = await canonical(session, sport)
    other_event = await repo.create_event(canonical_athlete_id=other_node.id)
    with pytest.raises(ValueError):
        await repo.resolve_observation(
            observation_id=observation.id,
            athlete_competitor_id=valid.id,
            canonical_transfer_id=other_event.id,
        )
    linked = await repo.resolve_observation(
        observation_id=observation.id,
        athlete_competitor_id=valid.id,
        canonical_transfer_id=event.id,
    )
    assert linked.canonical_transfer_id == event.id
    refreshed = await repo.record_observation(
        source_id=sources[0].id,
        fetched_at=NOW,
        transfer=ProviderTransfer(
            athlete_external_id="p1", external_id="event", athlete_name="Rename"
        ),
    )
    assert refreshed.canonical_transfer_id == event.id
    assert await count(session, Athlete) == 0


async def test_event_rejects_wrong_types_sports_and_seasons(session):
    sport, _, node = await seed(session)
    team = await canonical(session, sport, "team")
    other_sport = await add(session, Sport, slug="rugby", name="Rugby")
    other_team = await canonical(session, other_sport, "team")
    competition = await add(
        session,
        SportsCanonicalCompetition,
        sport_id=other_sport.id,
        canonical_key="other-competition",
        name="Cup",
        normalized_name="cup",
    )
    season = await add(
        session,
        SportsSeason,
        canonical_competition_id=competition.id,
        label="2026",
        normalized_label="2026",
    )
    repo = SMS24TransfersRepository(session)
    for values in (
        {"canonical_athlete_id": team.id},
        {"canonical_athlete_id": node.id, "from_club_id": node.id},
        {"canonical_athlete_id": node.id, "to_club_id": other_team.id},
        {"canonical_athlete_id": node.id, "season_id": season.id},
    ):
        with pytest.raises(ValueError):
            await repo.create_event(**values)
    assert await count(session, SportsCanonicalTransfer) == 0
    event = await repo.create_event(canonical_athlete_id=node.id, to_club_id=team.id)
    assert event.to_club_id == team.id


@pytest.mark.parametrize(
    "changes",
    [
        {"movement_type": "made-up"},
        {"status": "made-up"},
        {"fee_amount": -1},
        {"fee_currency": "usd"},
        {"canonical_athlete_id": uuid.uuid4()},
    ],
)
async def test_database_rejects_invalid_event_facts(session, changes):
    _, _, node = await seed(session)
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                insert(SportsCanonicalTransfer).values(
                    **{"canonical_athlete_id": node.id, **changes}
                )
            )


async def test_existing_team_resolver_behavior_unchanged(session):
    sport, sources, _ = await seed(session)
    repo = SMS24IngestionRepository(session)
    resolved = [
        await repo.resolve_canonical_competitor(
            source_id=source.id,
            sport_id=sport.id,
            participant=ProviderParticipant(
                external_id=str(i), name="Same Club", country_code="CI"
            ),
        )
        for i, source in enumerate(sources)
    ]
    assert resolved[0].id == resolved[1].id
    assert resolved[0].identity_scope == "verified_context"


async def test_observation_database_identity_constraints(session):
    _, sources, _ = await seed(session)
    values = dict(
        source_id=sources[0].id,
        observation_key="opaque",
        external_id="event",
        athlete_external_id="player",
        fetched_at=NOW,
    )
    await session.execute(insert(SportsTransferObservation).values(**values))
    for changes in (
        {},  # duplicate source + key
        {"observation_key": "another-key"},  # duplicate source + external ID
        {"observation_key": "new", "external_id": None},  # no stable identity
        {"observation_key": "new", "external_id": " ", "record_reference": "valid"},
        {"observation_key": "new", "external_id": "new", "athlete_external_id": " "},
        {"source_id": uuid.uuid4()},
        {"observation_key": "new", "external_id": "new", "athlete_competitor_id": uuid.uuid4()},
    ):
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.execute(
                    insert(SportsTransferObservation).values(**{**values, **changes})
                )
    await session.execute(
        insert(SportsTransferObservation).values(**{**values, "source_id": sources[1].id})
    )
    assert await count(session, SportsTransferObservation) == 2


async def test_explicit_verified_link_and_reference_deletion_protection(session):
    sport, sources, node = await seed(session)
    person = await human(session, sport)
    repo = SMS24TransfersRepository(session)
    link = await repo.link_athlete(
        athlete_id=person.id,
        canonical_competitor_id=node.id,
        method="institutional_review",
        established_by="institution-reviewer",
        evidence_reference="review:42",
        status="verified",
        verified_at=NOW,
    )
    assert link.status == "verified"
    await repo.record_observation(
        source_id=sources[0].id,
        fetched_at=NOW,
        transfer=ProviderTransfer(athlete_external_id="player", external_id="event"),
    )
    for model, identity in (
        (Athlete, person.id),
        (SportsCanonicalCompetitor, node.id),
        (SportsDataSource, sources[0].id),
    ):
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.execute(model.__table__.delete().where(model.id == identity))
    assert await count(session, AthleteCountryEligibility) == 0
    assert await count(session, AthletePassport) == 0
