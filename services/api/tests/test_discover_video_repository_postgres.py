"""PostgreSQL tests for public athlete videos in SMS Discover."""

import uuid

import pytest

from app.models.country import Country
from app.models.discover_video import DiscoverVideo
from app.models.sport import Sport
from app.repositories.discover_video_repository import DiscoverVideoRepository
from tests import test_sms24_player_statistics_postgres as foundation
from tests.test_discover_athlete_repository_postgres import (
    create_discoverable_athlete,
)
from tests.test_sms24_transfers_postgres import add

previous_connection = foundation.previous_connection


@pytest.fixture
async def connection(previous_connection):
    await previous_connection.run_sync(
        lambda sync: DiscoverVideo.__table__.create(sync, checkfirst=True)
    )
    yield previous_connection


@pytest.fixture
async def session(connection):
    async with foundation.AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        yield session


async def create_video(
    session,
    *,
    athlete_id,
    suffix,
    publication_status="published",
    moderation_status="approved",
    visibility="public",
    is_active=True,
):
    return await add(
        session,
        DiscoverVideo,
        athlete_id=athlete_id,
        video_url=f"https://example.com/{suffix}.mp4",
        thumbnail_url=f"https://example.com/{suffix}.jpg",
        caption=f"Video {suffix}",
        duration_seconds=20,
        publication_status=publication_status,
        moderation_status=moderation_status,
        visibility=visibility,
        is_active=is_active,
    )


@pytest.mark.asyncio
async def test_list_public_by_athlete_id_enforces_publication_rules(session):
    sport = await add(
        session,
        Sport,
        name=f"Football {uuid.uuid4()}",
        slug=f"football-{uuid.uuid4()}",
        is_active=True,
    )
    country = await add(
        session,
        Country,
        iso2="CI",
        iso3=f"C{uuid.uuid4().hex[:2]}".upper(),
        name=f"Côte d'Ivoire {uuid.uuid4()}",
        continent_code="AF",
        is_active=True,
    )

    athlete, _ = await create_discoverable_athlete(
        session,
        sport=sport,
        country=country,
        suffix="public-video",
    )
    other_athlete, _ = await create_discoverable_athlete(
        session,
        sport=sport,
        country=country,
        suffix="other-video",
    )

    expected = await create_video(
        session,
        athlete_id=athlete.id,
        suffix="eligible",
    )

    await create_video(
        session,
        athlete_id=athlete.id,
        suffix="draft",
        publication_status="draft",
    )
    await create_video(
        session,
        athlete_id=athlete.id,
        suffix="pending",
        moderation_status="pending",
    )
    await create_video(
        session,
        athlete_id=athlete.id,
        suffix="private",
        visibility="private",
    )
    await create_video(
        session,
        athlete_id=athlete.id,
        suffix="inactive",
        is_active=False,
    )
    await create_video(
        session,
        athlete_id=other_athlete.id,
        suffix="other-athlete",
    )

    repository = DiscoverVideoRepository(session)

    results = await repository.list_public_by_athlete_id(athlete.id)

    assert [video.id for video in results] == [expected.id]
    assert all(video.athlete_id == athlete.id for video in results)
    assert all(video.publication_status == "published" for video in results)
    assert all(video.moderation_status == "approved" for video in results)
    assert all(video.visibility == "public" for video in results)
    assert all(video.is_active is True for video in results)
