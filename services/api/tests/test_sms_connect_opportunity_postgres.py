"""Opportunity conversion, audit and 0040 round trips on disposable PostgreSQL."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, ForbiddenError
from app.models.sms_connect_athlete_response_event import (
    SMSConnectAthleteResponseEvent as ResponseEvent,
)
from app.models.sms_connect_opportunity import SMSConnectOpportunity as Opportunity
from app.models.sms_connect_opportunity import SMSConnectOpportunityEvent as Event
from app.schemas.sms_connect import (
    SMSConnectAthleteResponseRequest,
    SMSConnectOpportunityTransitionRequest,
)
from app.services.sms_connect_service import SMSConnectService
from tests import test_sms_connect_athlete_response_postgres as foundation

connection = foundation.connection
session = foundation.session


async def respond(service, interest, owner, decision):
    return await service.respond_to_interest(
        interest_id=interest.id,
        athlete_user_id=owner.id,
        data=SMSConnectAthleteResponseRequest(athlete_response=decision),
    )


async def only_opportunity(session):
    return (await session.scalars(select(Opportunity))).one()


async def events(session):
    return (await session.scalars(select(Event).order_by(Event.created_at, Event.id))).all()


async def test_conversion_replay_withdrawal_reactivation(session):
    owner, _, interest = await foundation.seed(session)
    service = SMSConnectService(session)
    await respond(service, interest, owner, "declined")
    assert await session.scalar(select(func.count()).select_from(Opportunity)) == 0
    await respond(service, interest, owner, "interested")
    opportunity = await only_opportunity(session)
    identity, opened, updated = opportunity.id, opportunity.opened_at, opportunity.updated_at
    assert opportunity.status == "active" and opportunity.closed_at is None
    first_response_at = interest.athlete_responded_at
    await respond(service, interest, owner, "interested")
    await session.refresh(opportunity)
    assert opportunity.updated_at == updated and interest.athlete_responded_at == first_response_at
    assert len(await events(session)) == 1
    await respond(service, interest, owner, "declined")
    assert opportunity.status == "withdrawn" and opportunity.closed_at is not None
    await respond(service, interest, owner, "interested")
    assert opportunity.status == "active" and opportunity.closed_at is None
    assert opportunity.id == identity and opportunity.opened_at == opened
    assert await session.scalar(select(func.count()).select_from(Opportunity)) == 1
    audit = await events(session)
    assert [(e.from_status, e.to_status, e.source) for e in audit] == [
        (None, "active", "athlete_consent"),
        ("active", "withdrawn", "athlete_withdrawal"),
        ("withdrawn", "active", "athlete_reactivation"),
    ]
    assert all(e.actor_user_id == owner.id for e in audit)
    assert interest.status == "delivered"


@pytest.mark.parametrize("outcome", ["successful", "unsuccessful"])
async def test_terminal_outcome_is_not_changed_by_new_decisions(session, outcome):
    owner, _, interest = await foundation.seed(session)
    service = SMSConnectService(session)
    service.roles.get_verified_admin_role = AsyncMock(return_value=SimpleNamespace(role="admin"))
    await respond(service, interest, owner, "interested")
    opportunity = await only_opportunity(session)
    for status in ("progressing", outcome):
        await service.transition_opportunity(
            opportunity_id=opportunity.id,
            admin_user_id=owner.id,
            data=SMSConnectOpportunityTransitionRequest(status=status),
        )
    closed_at = opportunity.closed_at
    await respond(service, interest, owner, "declined")
    await respond(service, interest, owner, "interested")
    assert opportunity.status == outcome and opportunity.closed_at == closed_at
    assert len(await events(session)) == 3


async def test_progressing_can_be_withdrawn(session):
    owner, _, interest = await foundation.seed(session)
    service = SMSConnectService(session)
    service.roles.get_verified_admin_role = AsyncMock(return_value=SimpleNamespace(role="admin"))
    await respond(service, interest, owner, "interested")
    opportunity = await only_opportunity(session)
    await service.transition_opportunity(
        opportunity_id=opportunity.id,
        admin_user_id=owner.id,
        data=SMSConnectOpportunityTransitionRequest(status="progressing"),
    )
    await respond(service, interest, owner, "declined")
    assert opportunity.status == "withdrawn" and opportunity.closed_at is not None


@pytest.mark.parametrize("status", ["submitted", "under_review", "approved", "rejected", "closed"])
async def test_not_delivered_never_converts(session, status):
    owner, _, interest = await foundation.seed(session, status)
    with pytest.raises(ConflictError):
        await respond(SMSConnectService(session), interest, owner, "interested")
    assert await session.scalar(select(func.count()).select_from(Opportunity)) == 0


async def test_owner_and_read_scopes(session):
    owner, requester, interest = await foundation.seed(session)
    service = SMSConnectService(session)
    with pytest.raises(ForbiddenError):
        await respond(service, interest, requester, "interested")
    await respond(service, interest, owner, "interested")
    assert len(await service.list_athlete_opportunities(owner.id)) == 1
    assert len(await service.list_my_opportunities(requester.id)) == 1
    for unrelated in (uuid.uuid4(), requester.id):
        assert await service.list_athlete_opportunities(unrelated) == []
    for unrelated in (uuid.uuid4(), owner.id):
        assert await service.list_my_opportunities(unrelated) == []
    for row in await service.list_my_opportunities(requester.id):
        assert (
            not {"requester_user_id", "user_id", "athlete_user_id", "email", "phone", "whatsapp"}
            & row.keys()
        )


@pytest.mark.parametrize("failure", ["create", "audit"])
async def test_atomic_rollback(session, monkeypatch, failure):
    owner, _, interest = await foundation.seed(session)
    service = SMSConnectService(session)
    method = "create" if failure == "create" else "add_event"
    original = getattr(service.opportunities, method)

    async def broken(value):
        await original(value)
        raise RuntimeError("Injected failure")

    monkeypatch.setattr(service.opportunities, method, broken)
    with pytest.raises(RuntimeError):
        async with session.begin_nested():
            await respond(service, interest, owner, "interested")
    await session.refresh(interest)
    assert interest.athlete_response == "pending" and interest.athlete_responded_at is None
    for model in (Opportunity, Event, ResponseEvent):
        assert await session.scalar(select(func.count()).select_from(model)) == 0


async def test_unique_interest_and_foreign_key_protect_provenance(session):
    owner, _, interest = await foundation.seed(session)
    await respond(SMSConnectService(session), interest, owner, "interested")
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(Opportunity(interest_id=interest.id))
            await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.delete(interest)
            await session.flush()
    assert await session.scalar(select(func.count()).select_from(Opportunity)) == 1


async def test_0040_roundtrip(connection):
    await connection.run_sync(lambda sync: foundation.migrate(sync, foundation.M39))
    assert foundation.M40.down_revision == foundation.M39.revision
    for _ in range(2):
        await connection.run_sync(lambda sync: foundation.migrate(sync, foundation.M40))

        def verify(sync):
            inspector = inspect(sync)
            for model in (Opportunity, Event):
                assert {c["name"] for c in inspector.get_columns(model.__tablename__)} == set(
                    model.__table__.columns.keys()
                )
            assert inspector.get_unique_constraints(Opportunity.__tablename__)[0][
                "column_names"
            ] == ["interest_id"]

        await connection.run_sync(verify)
        await connection.run_sync(
            lambda sync: foundation.migrate(sync, foundation.M40, "downgrade")
        )
        assert await connection.run_sync(
            lambda sync: inspect(sync).has_table("sms_connect_interests")
        )
        assert not await connection.run_sync(
            lambda sync: inspect(sync).has_table(Opportunity.__tablename__)
        )
    await connection.run_sync(lambda sync: foundation.migrate(sync, foundation.M40))


async def test_concurrent_consent_creates_one_opportunity_and_one_event():
    """Two actual transactions share a committed, isolated disposable schema."""
    import asyncio
    import os

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    url = os.environ.get("SMS24_MIGRATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Disposable PostgreSQL is required")
    engine = create_async_engine(url, poolclass=NullPool)
    schema = f"sms_connect_0040_concurrency_{uuid.uuid4().hex}"
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            await conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            await conn.run_sync(
                lambda sync: foundation.Base.metadata.create_all(
                    sync,
                    tables=[
                        m.__table__
                        for m in (
                            foundation.Sport,
                            foundation.Country,
                            foundation.User,
                            foundation.Athlete,
                        )
                    ],
                )
            )
            for migration in (foundation.M20, foundation.M21, foundation.M39, foundation.M40):
                await conn.run_sync(lambda sync, m=migration: foundation.migrate(sync, m))
            async with AsyncSession(bind=conn, expire_on_commit=False) as seed_session:
                owner, _, interest = await foundation.seed(seed_session)
                owner_id, interest_id = owner.id, interest.id
        start = asyncio.Event()

        async def request():
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await session.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                await session.execute(text("SET LOCAL lock_timeout TO '10s'"))
                await start.wait()
                await SMSConnectService(session).respond_to_interest(
                    interest_id=interest_id,
                    athlete_user_id=owner_id,
                    data=SMSConnectAthleteResponseRequest(athlete_response="interested"),
                )
                await session.commit()

        tasks = [asyncio.create_task(request()) for _ in range(2)]
        start.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 30)
        assert results == [None, None]
        async with engine.connect() as conn:
            await conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            for model in (Opportunity, Event, ResponseEvent):
                assert await conn.scalar(select(func.count()).select_from(model)) == 1
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


async def test_admin_audit_failure_rolls_back_opportunity_status(session, monkeypatch):
    owner, _, interest = await foundation.seed(session)
    service = SMSConnectService(session)
    service.roles.get_verified_admin_role = AsyncMock(return_value=SimpleNamespace(role="admin"))
    await respond(service, interest, owner, "interested")
    opportunity = await only_opportunity(session)
    original = service.opportunities.add_event

    async def broken(event):
        await original(event)
        raise RuntimeError("audit failure")

    monkeypatch.setattr(service.opportunities, "add_event", broken)
    with pytest.raises(RuntimeError):
        async with session.begin_nested():
            await service.transition_opportunity(
                opportunity_id=opportunity.id,
                admin_user_id=owner.id,
                data=SMSConnectOpportunityTransitionRequest(status="unsuccessful"),
            )
    await session.refresh(opportunity)
    assert opportunity.status == "active" and opportunity.closed_at is None
    assert len(await events(session)) == 1
