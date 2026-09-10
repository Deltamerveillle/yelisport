"""Real PostgreSQL tests for the SMS24 historical canonical backfill."""

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models.sport import Sport
from app.models.sports_live import (
    SportsCanonicalFixture,
    SportsCompetitor,
    SportsDataSource,
    SportsFixture,
    SportsFixtureParticipant,
)
from app.sms24.backfill import (
    backfill_historical_canonical_fixtures,
)


PREFIX = "sms24-backfill-pg-"

_engine = create_async_engine(
    get_settings().database_url,
    poolclass=NullPool,
)

SessionFactory = async_sessionmaker(
    _engine,
    expire_on_commit=False,
)


async def cleanup_test_data(
    session,
    *,
    sport_id,
    source_ids,
):
    fixture_ids = select(SportsFixture.id).where(
        SportsFixture.sport_id == sport_id
    )

    await session.execute(
        delete(SportsFixtureParticipant).where(
            SportsFixtureParticipant.fixture_id.in_(fixture_ids)
        )
    )

    await session.execute(
        delete(SportsFixture).where(
            SportsFixture.sport_id == sport_id
        )
    )

    for source_id in source_ids:
        await session.execute(
            delete(SportsCompetitor).where(
                SportsCompetitor.source_id == source_id
            )
        )

    await session.execute(
        delete(SportsCanonicalFixture).where(
            SportsCanonicalFixture.sport_id == sport_id
        )
    )

    await session.execute(
        delete(SportsDataSource).where(
            SportsDataSource.id.in_(source_ids)
        )
    )

    await session.execute(
        delete(Sport).where(
            Sport.id == sport_id
        )
    )

    await session.commit()


@pytest.mark.asyncio
async def test_historical_backfill_merges_cross_provider_observations_and_is_idempotent():
    async with SessionFactory() as session:
        sport_id = uuid.uuid4()
        primary_source_id = uuid.uuid4()
        secondary_source_id = uuid.uuid4()

        sport = Sport(
            id=sport_id,
            slug=f"{PREFIX}football-{uuid.uuid4().hex[:8]}",
            name="SMS24 Backfill PostgreSQL Test",
            description="Temporary historical backfill test sport",
            is_active=True,
        )

        primary = SportsDataSource(
            id=primary_source_id,
            slug=f"{PREFIX}primary-{uuid.uuid4().hex[:8]}",
            name="Primary Historical Provider",
            provider_type="test",
            priority=10,
            is_active=True,
            health_status="healthy",
        )

        secondary = SportsDataSource(
            id=secondary_source_id,
            slug=f"{PREFIX}secondary-{uuid.uuid4().hex[:8]}",
            name="Secondary Historical Provider",
            provider_type="test",
            priority=20,
            is_active=True,
            health_status="healthy",
        )

        session.add_all([sport, primary, secondary])
        await session.flush()

        starts_at = datetime(
            2026,
            9,
            10,
            18,
            45,
            tzinfo=timezone.utc,
        )

        primary_home = SportsCompetitor(
            id=uuid.uuid4(),
            sport_id=sport_id,
            source_id=primary_source_id,
            external_id="primary-rangers",
            competitor_type="team",
            name="Rangers",
            metadata_json={},
        )

        primary_away = SportsCompetitor(
            id=uuid.uuid4(),
            sport_id=sport_id,
            source_id=primary_source_id,
            external_id="primary-st-mirren",
            competitor_type="team",
            name="ST Mirren",
            metadata_json={},
        )

        secondary_home = SportsCompetitor(
            id=uuid.uuid4(),
            sport_id=sport_id,
            source_id=secondary_source_id,
            external_id="secondary-rangers",
            competitor_type="team",
            name="Rangers",
            metadata_json={},
        )

        secondary_away = SportsCompetitor(
            id=uuid.uuid4(),
            sport_id=sport_id,
            source_id=secondary_source_id,
            external_id="secondary-st-mirren",
            competitor_type="team",
            name="St. Mirren",
            metadata_json={},
        )

        session.add_all(
            [
                primary_home,
                primary_away,
                secondary_home,
                secondary_away,
            ]
        )
        await session.flush()

        primary_fixture = SportsFixture(
            id=uuid.uuid4(),
            source_id=primary_source_id,
            sport_id=sport_id,
            competition_id=None,
            canonical_fixture_id=None,
            external_id="primary-fixture-001",
            name="Rangers vs ST Mirren",
            starts_at=starts_at,
            status="scheduled",
            live_clock=None,
            venue=None,
            result_json={},
            metadata_json={},
            source_updated_at=None,
            fetched_at=starts_at,
        )

        secondary_fixture = SportsFixture(
            id=uuid.uuid4(),
            source_id=secondary_source_id,
            sport_id=sport_id,
            competition_id=None,
            canonical_fixture_id=None,
            external_id="secondary-fixture-999",
            name="Rangers vs St. Mirren",
            starts_at=starts_at,
            status="scheduled",
            live_clock=None,
            venue=None,
            result_json={},
            metadata_json={},
            source_updated_at=None,
            fetched_at=starts_at,
        )

        session.add_all(
            [
                primary_fixture,
                secondary_fixture,
            ]
        )
        await session.flush()

        session.add_all(
            [
                SportsFixtureParticipant(
                    id=uuid.uuid4(),
                    fixture_id=primary_fixture.id,
                    competitor_id=primary_home.id,
                    position=0,
                    role="home",
                    score_json={},
                ),
                SportsFixtureParticipant(
                    id=uuid.uuid4(),
                    fixture_id=primary_fixture.id,
                    competitor_id=primary_away.id,
                    position=1,
                    role="away",
                    score_json={},
                ),
                SportsFixtureParticipant(
                    id=uuid.uuid4(),
                    fixture_id=secondary_fixture.id,
                    competitor_id=secondary_home.id,
                    position=0,
                    role="home",
                    score_json={},
                ),
                SportsFixtureParticipant(
                    id=uuid.uuid4(),
                    fixture_id=secondary_fixture.id,
                    competitor_id=secondary_away.id,
                    position=1,
                    role="away",
                    score_json={},
                ),
            ]
        )

        await session.commit()

        first_result = await backfill_historical_canonical_fixtures(
            session
        )

        assert first_result.processed == 2
        assert first_result.resolved == 2
        assert first_result.skipped == 0

        await session.commit()

        await session.refresh(primary_fixture)
        await session.refresh(secondary_fixture)

        assert primary_fixture.canonical_fixture_id is not None
        assert (
            primary_fixture.canonical_fixture_id
            == secondary_fixture.canonical_fixture_id
        )

        canonical_rows = list(
            (
                await session.execute(
                    select(SportsCanonicalFixture).where(
                        SportsCanonicalFixture.sport_id == sport_id
                    )
                )
            ).scalars().all()
        )

        assert len(canonical_rows) == 1

        second_result = await backfill_historical_canonical_fixtures(
            session
        )

        assert second_result.processed == 0
        assert second_result.resolved == 0
        assert second_result.skipped == 0

        await session.rollback()

        await cleanup_test_data(
            session,
            sport_id=sport_id,
            source_ids=[
                primary_source_id,
                secondary_source_id,
            ],
        )


@pytest.mark.asyncio
async def test_historical_backfill_skips_fixture_with_insufficient_participants():
    async with SessionFactory() as session:
        sport_id = uuid.uuid4()
        source_id = uuid.uuid4()

        sport = Sport(
            id=sport_id,
            slug=f"{PREFIX}incomplete-{uuid.uuid4().hex[:8]}",
            name="SMS24 Backfill Incomplete Test",
            description="Temporary incomplete historical fixture test",
            is_active=True,
        )

        source = SportsDataSource(
            id=source_id,
            slug=f"{PREFIX}source-{uuid.uuid4().hex[:8]}",
            name="Incomplete Historical Provider",
            provider_type="test",
            priority=999,
            is_active=True,
            health_status="healthy",
        )

        session.add_all([sport, source])
        await session.flush()

        competitor = SportsCompetitor(
            id=uuid.uuid4(),
            sport_id=sport_id,
            source_id=source_id,
            external_id="only-participant",
            competitor_type="team",
            name="Only Team",
            metadata_json={},
        )

        session.add(competitor)
        await session.flush()

        fixture = SportsFixture(
            id=uuid.uuid4(),
            source_id=source_id,
            sport_id=sport_id,
            competition_id=None,
            canonical_fixture_id=None,
            external_id="incomplete-fixture",
            name="Incomplete fixture",
            starts_at=datetime(
                2026,
                9,
                10,
                22,
                0,
                tzinfo=timezone.utc,
            ),
            status="scheduled",
            live_clock=None,
            venue=None,
            result_json={},
            metadata_json={},
            source_updated_at=None,
            fetched_at=datetime(
                2026,
                9,
                10,
                21,
                0,
                tzinfo=timezone.utc,
            ),
        )

        session.add(fixture)
        await session.flush()

        session.add(
            SportsFixtureParticipant(
                id=uuid.uuid4(),
                fixture_id=fixture.id,
                competitor_id=competitor.id,
                position=0,
                role="home",
                score_json={},
            )
        )

        await session.commit()

        result = await backfill_historical_canonical_fixtures(
            session
        )

        assert result.processed == 1
        assert result.resolved == 0
        assert result.skipped == 1

        await session.refresh(fixture)

        assert fixture.canonical_fixture_id is None

        canonical_rows = list(
            (
                await session.execute(
                    select(SportsCanonicalFixture).where(
                        SportsCanonicalFixture.sport_id == sport_id
                    )
                )
            ).scalars().all()
        )

        assert canonical_rows == []

        await session.rollback()

        await cleanup_test_data(
            session,
            sport_id=sport_id,
            source_ids=[source_id],
        )
