"""0039 and response persistence only in disposable rollback-only PostgreSQL schemas."""

import importlib
import os
import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.models.athlete import Athlete
from app.models.country import Country
from app.models.sms_connect_athlete_response_event import SMSConnectAthleteResponseEvent as Event
from app.models.sms_connect_interest import SMSConnectInterest as Interest
from app.models.sms_connect_interest_event import SMSConnectInterestEvent as AdminEvent
from app.models.sport import Sport
from app.models.user import User
from app.repositories.sms_connect_interest_repository import SMSConnectInterestRepository
from app.schemas.sms_connect import SMSConnectAthleteResponseRequest
from app.services.sms_connect_service import SMSConnectService

M20 = importlib.import_module(
    "app.db.migrations.versions.20260904_0020_create_sms_connect_interests"
)
M21 = importlib.import_module(
    "app.db.migrations.versions.20260904_0021_create_sms_connect_interest_events"
)
M39 = importlib.import_module(
    "app.db.migrations.versions.20260926_0039_add_sms_connect_athlete_response"
)


M40 = importlib.import_module(
    "app.db.migrations.versions.20260926_0040_add_sms_connect_opportunities"
)


def migrate(connection, migration, direction="upgrade"):
    with Operations.context(MigrationContext.configure(connection)):
        getattr(migration, direction)()


@pytest.fixture
async def connection():
    url = os.environ.get("SMS24_MIGRATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set SMS24_MIGRATION_TEST_DATABASE_URL to disposable PostgreSQL")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                schema = f"sms_connect_0039_test_{uuid.uuid4().hex}"
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                await connection.run_sync(
                    lambda sync: Base.metadata.create_all(
                        sync,
                        tables=[m.__table__ for m in (Sport, Country, User, Athlete)],
                    )
                )
                for migration in (M20, M21):
                    await connection.run_sync(lambda sync, m=migration: migrate(sync, m))
                yield connection
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
async def session(connection):
    await connection.run_sync(lambda sync: migrate(sync, M39))
    await connection.run_sync(lambda sync: migrate(sync, M40))
    async with AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as session:
        yield session


async def seed(session, status="delivered"):
    owner = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.test")
    requester = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.test")
    sport = Sport(slug="football", name="Football")
    session.add_all([owner, requester, sport])
    await session.flush()
    athlete = Athlete(user_id=owner.id, sport_id=sport.id, first_name="A", last_name="B")
    session.add(athlete)
    await session.flush()
    interest = Interest(
        athlete_id=athlete.id,
        requester_user_id=requester.id,
        requester_role="club",
        interest_type="trial",
        organization_name="Club",
        subject="Trial",
        message="SMS mediated opportunity",
        status=status,
    )
    session.add(interest)
    await session.flush()
    return owner, requester, interest


@pytest.mark.parametrize("decision", ["interested", "declined"])
async def test_persistence_audit_replay_and_independent_status(session, decision):
    owner, requester, interest = await seed(session)
    service = SMSConnectService(session)

    async def respond(value):
        return await service.respond_to_interest(
            interest_id=interest.id,
            athlete_user_id=owner.id,
            data=SMSConnectAthleteResponseRequest(athlete_response=value),
        )

    await respond(decision)
    await session.commit()
    await session.refresh(interest)
    assert interest.status == "delivered" and interest.athlete_response == decision
    timestamp = interest.athlete_responded_at
    assert timestamp.utcoffset().total_seconds() == 0
    await respond(decision)
    assert interest.athlete_responded_at == timestamp
    events = (await session.scalars(select(Event))).all()
    assert len(events) == 1
    assert events[0].actor_user_id == owner.id and events[0].from_response == "pending"
    assert events[0].to_response == decision and events[0].created_at == timestamp
    assert await session.scalar(select(func.count()).select_from(AdminEvent)) == 0
    assert await session.scalar(select(func.count()).select_from(User)) == 2
    assert await session.scalar(select(func.count()).select_from(Athlete)) == 1
    await respond("declined" if decision == "interested" else "interested")
    assert await session.scalar(select(func.count()).select_from(Event)) == 2


async def test_rollback_is_atomic_when_audit_fails(session, monkeypatch):
    owner, _, interest = await seed(session)
    service = SMSConnectService(session)
    original = service.interests.add_athlete_response_event

    async def broken(event):
        await original(event)
        raise RuntimeError("audit transaction failure")

    monkeypatch.setattr(service.interests, "add_athlete_response_event", broken)
    with pytest.raises(RuntimeError):
        async with session.begin_nested():
            await service.respond_to_interest(
                interest_id=interest.id,
                athlete_user_id=owner.id,
                data=SMSConnectAthleteResponseRequest(athlete_response="interested"),
            )
    await session.refresh(interest)
    assert interest.athlete_response == "pending" and interest.athlete_responded_at is None
    assert await session.scalar(select(func.count()).select_from(Event)) == 0


async def test_inbox_only_delivered_and_owned(session):
    owner, requester, interest = await seed(session)
    for status in ("submitted", "under_review", "approved", "rejected", "closed"):
        session.add(
            Interest(
                athlete_id=interest.athlete_id,
                requester_user_id=requester.id,
                requester_role="club",
                interest_type="trial",
                organization_name="Club",
                subject="Trial",
                message="Message",
                status=status,
            )
        )
    await session.flush()
    repository = SMSConnectInterestRepository(session)
    assert [row.id for row in await repository.list_for_athlete_user(owner.id)] == [interest.id]
    assert await repository.list_for_athlete_user(requester.id) == []


async def test_0039_roundtrip_constraints_indexes_and_model(connection):
    assert M39.revision == "20260926_0039" and M39.down_revision == "20260922_0038"
    for _ in range(2):
        await connection.run_sync(lambda sync: migrate(sync, M39))

        def verify(sync):
            inspector = inspect(sync)
            columns = {c["name"]: c for c in inspector.get_columns(Interest.__tablename__)}
            assert columns["athlete_response"]["nullable"] is False
            assert columns["athlete_response"]["type"].length == 30
            assert "pending" in columns["athlete_response"]["default"]
            assert columns["athlete_responded_at"]["type"].timezone is True
            assert columns["athlete_responded_at"]["nullable"] is True
            assert set(columns) == set(Interest.__table__.columns.keys())
            assert "ck_sms_connect_athlete_response" in {
                c["name"] for c in inspector.get_check_constraints(Interest.__tablename__)
            }
            assert "ix_sms_connect_interests_athlete_response" in {
                i["name"] for i in inspector.get_indexes(Interest.__tablename__)
            }
            assert {c["name"] for c in inspector.get_columns(Event.__tablename__)} == set(
                Event.__table__.columns.keys()
            )

        await connection.run_sync(verify)
        await connection.run_sync(lambda sync: migrate(sync, M39, "downgrade"))

        def verify_removed(sync):
            inspector = inspect(sync)
            assert not inspector.has_table(Event.__tablename__)
            assert inspector.has_table(AdminEvent.__tablename__)
            assert "athlete_response" not in {
                c["name"] for c in inspector.get_columns(Interest.__tablename__)
            }

        await connection.run_sync(verify_removed)
    await connection.run_sync(lambda sync: migrate(sync, M39))


@pytest.mark.parametrize("value", ["approved", "", None])
async def test_invalid_response_rejected_by_database(session, value):
    _, _, interest = await seed(session)
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            interest.athlete_response = value
            await session.flush()


async def test_upgrade_backfills_existing_interest_and_preserves_admin_audit(session):
    owner, _, interest = await seed(session)
    interest_id = interest.id
    event = AdminEvent(
        interest_id=interest_id,
        actor_user_id=owner.id,
        actor_role="admin",
        from_status="approved",
        to_status="delivered",
        note="SMS delivery",
    )
    session.add(event)
    await session.flush()
    connection = await session.connection()
    await connection.run_sync(lambda sync: migrate(sync, M39, "downgrade"))
    before = (await session.execute(text("SELECT * FROM sms_connect_interests"))).mappings().one()
    await connection.run_sync(lambda sync: migrate(sync, M39))
    after = (await session.execute(text("SELECT * FROM sms_connect_interests"))).mappings().one()
    assert all(after[key] == value for key, value in before.items())
    assert after["athlete_response"] == "pending" and after["athlete_responded_at"] is None
    assert await session.scalar(select(func.count()).select_from(AdminEvent)) == 1


@pytest.mark.parametrize(
    "previous,current",
    [("approved", "interested"), ("pending", "pending"), ("declined", "declined")],
)
async def test_audit_constraints(session, previous, current):
    owner, _, interest = await seed(session)
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                Event(
                    interest_id=interest.id,
                    actor_user_id=owner.id,
                    from_response=previous,
                    to_response=current,
                )
            )
            await session.flush()
