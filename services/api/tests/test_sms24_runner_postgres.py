"""PostgreSQL integration tests for SMS24 runner persistence."""

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models.sports_live import SportsDataSource
from app.sms24.runner import SMS24RunnerRepository


PREFIX = "sms24-pg-test-"

_test_engine = create_async_engine(
    get_settings().database_url,
    poolclass=NullPool,
)
TestSessionFactory = async_sessionmaker(
    _test_engine,
    expire_on_commit=False,
)


async def cleanup(session):
    await session.execute(
        delete(SportsDataSource).where(
            SportsDataSource.slug.like(f"{PREFIX}%")
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_postgres_orders_sources_by_priority():
    async with TestSessionFactory() as session:
        await cleanup(session)

        session.add_all(
            [
                SportsDataSource(
                    id=uuid.uuid4(),
                    slug=f"{PREFIX}secondary",
                    name="Secondary",
                    priority=20,
                    is_active=True,
                ),
                SportsDataSource(
                    id=uuid.uuid4(),
                    slug=f"{PREFIX}primary",
                    name="Primary",
                    priority=10,
                    is_active=True,
                ),
                SportsDataSource(
                    id=uuid.uuid4(),
                    slug=f"{PREFIX}disabled",
                    name="Disabled",
                    priority=1,
                    is_active=False,
                ),
            ]
        )
        await session.commit()

        repository = SMS24RunnerRepository(session)
        sources = await repository.list_active_sources()

        filtered = [
            slug
            for slug in sources
            if slug.startswith(PREFIX)
        ]

        assert filtered == [
            f"{PREFIX}primary",
            f"{PREFIX}secondary",
        ]

        await cleanup(session)


@pytest.mark.asyncio
async def test_postgres_persists_degraded_health_state():
    async with TestSessionFactory() as session:
        await cleanup(session)

        slug = f"{PREFIX}degraded"

        source = SportsDataSource(
            id=uuid.uuid4(),
            slug=slug,
            name="Degraded",
            priority=10,
            is_active=True,
            health_status="healthy",
        )

        session.add(source)
        await session.commit()

        repository = SMS24RunnerRepository(session)

        checked_at = datetime(
            2026,
            9,
            6,
            23,
            30,
            tzinfo=timezone.utc,
        )

        await repository.mark_failure(
            slug,
            checked_at=checked_at,
        )
        await repository.commit()

    async with TestSessionFactory() as verification:
        result = await verification.execute(
            select(SportsDataSource).where(
                SportsDataSource.slug == slug
            )
        )
        persisted = result.scalar_one()

        assert persisted.health_status == "degraded"
        assert persisted.last_failure_at == checked_at
        assert persisted.last_checked_at == checked_at

        await cleanup(verification)


@pytest.mark.asyncio
async def test_postgres_persists_unavailable_health_state():
    async with TestSessionFactory() as session:
        await cleanup(session)

        slug = f"{PREFIX}unavailable"

        source = SportsDataSource(
            id=uuid.uuid4(),
            slug=slug,
            name="Unavailable",
            priority=10,
            is_active=True,
            health_status="healthy",
        )

        session.add(source)
        await session.commit()

        repository = SMS24RunnerRepository(session)

        checked_at = datetime(
            2026,
            9,
            6,
            23,
            45,
            tzinfo=timezone.utc,
        )

        await repository.mark_unavailable(
            slug,
            checked_at=checked_at,
        )
        await repository.commit()

    async with TestSessionFactory() as verification:
        result = await verification.execute(
            select(SportsDataSource).where(
                SportsDataSource.slug == slug
            )
        )
        persisted = result.scalar_one()

        assert persisted.health_status == "unavailable"
        assert persisted.last_failure_at == checked_at
        assert persisted.last_checked_at == checked_at

        await cleanup(verification)
