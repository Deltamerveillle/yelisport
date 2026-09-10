"""Real PostgreSQL tests for SMS24 public canonical fixture reads."""

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models.sport import Sport
from app.models.sports_live import (
    SportsCanonicalFixture,
    SportsDataSource,
    SportsFixture,
)
from app.repositories.sms24_live_repository import SMS24LiveRepository


PREFIX = "sms24-public-canonical-"

_engine = create_async_engine(
    get_settings().database_url,
    poolclass=NullPool,
)

SessionFactory = async_sessionmaker(
    _engine,
    expire_on_commit=False,
)


@pytest.mark.asyncio
async def test_list_fixtures_returns_one_public_row_per_canonical_fixture():
    async with SessionFactory() as session:
        sport_id = uuid.uuid4()
        canonical_id = uuid.uuid4()

        sport = Sport(
            id=sport_id,
            slug=f"{PREFIX}football-{uuid.uuid4().hex[:8]}",
            name="SMS24 Public Canonical Test",
            description="Temporary repository integration-test sport",
            is_active=True,
        )

        primary = SportsDataSource(
            id=uuid.uuid4(),
            slug=f"{PREFIX}primary-{uuid.uuid4().hex[:8]}",
            name="Primary Provider",
            provider_type="test",
            priority=10,
            is_active=True,
            health_status="healthy",
        )

        secondary = SportsDataSource(
            id=uuid.uuid4(),
            slug=f"{PREFIX}secondary-{uuid.uuid4().hex[:8]}",
            name="Secondary Provider",
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
            20,
            0,
            tzinfo=timezone.utc,
        )

        canonical = SportsCanonicalFixture(
            id=canonical_id,
            sport_id=sport_id,
            canonical_key=f"sms24:{uuid.uuid4().hex}",
            participant_signature="a" * 64,
            starts_at=starts_at,
        )

        session.add(canonical)
        await session.flush()

        # Same real match, observed by two different providers.
        primary_fixture = SportsFixture(
            id=uuid.uuid4(),
            source_id=primary.id,
            sport_id=sport_id,
            competition_id=None,
            canonical_fixture_id=canonical_id,
            external_id="primary-match-001",
            name="Primary representation",
            starts_at=starts_at,
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
                20,
                1,
                tzinfo=timezone.utc,
            ),
        )

        secondary_fixture = SportsFixture(
            id=uuid.uuid4(),
            source_id=secondary.id,
            sport_id=sport_id,
            competition_id=None,
            canonical_fixture_id=canonical_id,
            external_id="secondary-match-999",
            name="Secondary representation",
            starts_at=starts_at,
            status="scheduled",
            live_clock=None,
            venue=None,
            result_json={},
            metadata_json={},
            source_updated_at=None,
            # Deliberately fresher: provider priority still wins.
            fetched_at=datetime(
                2026,
                9,
                10,
                20,
                4,
                tzinfo=timezone.utc,
            ),
        )

        # Legacy/provider observation not yet canonicalized.
        legacy_fixture = SportsFixture(
            id=uuid.uuid4(),
            source_id=secondary.id,
            sport_id=sport_id,
            competition_id=None,
            canonical_fixture_id=None,
            external_id="legacy-match-001",
            name="Legacy independent fixture",
            starts_at=datetime(
                2026,
                9,
                10,
                21,
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
                20,
                5,
                tzinfo=timezone.utc,
            ),
        )

        session.add_all(
            [
                primary_fixture,
                secondary_fixture,
                legacy_fixture,
            ]
        )
        await session.commit()

        repository = SMS24LiveRepository(session)

        fixtures = await repository.list_fixtures(
            sport_slug=sport.slug,
            limit=50,
            offset=0,
        )

        # One canonical match + one independent legacy fixture.
        assert len(fixtures) == 2

        canonical_views = [
            fixture
            for fixture in fixtures
            if fixture.name != "Legacy independent fixture"
        ]

        assert len(canonical_views) == 1

        public_fixture = canonical_views[0]

        # Primary provider wins deterministically.
        assert public_fixture.id == primary_fixture.id
        assert public_fixture.source_slug == primary.slug
        assert public_fixture.name == "Primary representation"

        assert any(
            fixture.id == legacy_fixture.id
            for fixture in fixtures
        )

        # FK-safe cleanup.
        await session.execute(
            delete(SportsFixture).where(
                SportsFixture.sport_id == sport_id
            )
        )

        await session.execute(
            delete(SportsCanonicalFixture).where(
                SportsCanonicalFixture.id == canonical_id
            )
        )

        await session.execute(
            delete(SportsDataSource).where(
                SportsDataSource.id.in_(
                    [primary.id, secondary.id]
                )
            )
        )

        await session.execute(
            delete(Sport).where(
                Sport.id == sport_id
            )
        )

        await session.commit()


@pytest.mark.asyncio
async def test_list_fixtures_paginates_after_canonical_deduplication():
    async with SessionFactory() as session:
        sport_id = uuid.uuid4()

        sport = Sport(
            id=sport_id,
            slug=f"{PREFIX}pagination-{uuid.uuid4().hex[:8]}",
            name="SMS24 Pagination Test",
            description="Temporary repository pagination test",
            is_active=True,
        )

        primary = SportsDataSource(
            id=uuid.uuid4(),
            slug=f"{PREFIX}pagination-primary-{uuid.uuid4().hex[:8]}",
            name="Pagination Primary",
            provider_type="test",
            priority=10,
            is_active=True,
            health_status="healthy",
        )

        secondary = SportsDataSource(
            id=uuid.uuid4(),
            slug=f"{PREFIX}pagination-secondary-{uuid.uuid4().hex[:8]}",
            name="Pagination Secondary",
            provider_type="test",
            priority=20,
            is_active=True,
            health_status="healthy",
        )

        session.add_all([sport, primary, secondary])
        await session.flush()

        canonical_ids = [
            uuid.uuid4(),
            uuid.uuid4(),
        ]

        starts = [
            datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc),
            datetime(2026, 9, 10, 19, 0, tzinfo=timezone.utc),
        ]

        for index, canonical_id in enumerate(canonical_ids):
            session.add(
                SportsCanonicalFixture(
                    id=canonical_id,
                    sport_id=sport_id,
                    canonical_key=f"sms24:{uuid.uuid4().hex}",
                    participant_signature=chr(97 + index) * 64,
                    starts_at=starts[index],
                )
            )

        await session.flush()

        fixtures_to_add = []

        for index, canonical_id in enumerate(canonical_ids):
            fixtures_to_add.extend(
                [
                    SportsFixture(
                        id=uuid.uuid4(),
                        source_id=primary.id,
                        sport_id=sport_id,
                        competition_id=None,
                        canonical_fixture_id=canonical_id,
                        external_id=f"primary-page-{index}",
                        name=f"Canonical Match {index + 1} Primary",
                        starts_at=starts[index],
                        status="scheduled",
                        live_clock=None,
                        venue=None,
                        result_json={},
                        metadata_json={},
                        source_updated_at=None,
                        fetched_at=starts[index],
                    ),
                    SportsFixture(
                        id=uuid.uuid4(),
                        source_id=secondary.id,
                        sport_id=sport_id,
                        competition_id=None,
                        canonical_fixture_id=canonical_id,
                        external_id=f"secondary-page-{index}",
                        name=f"Canonical Match {index + 1} Secondary",
                        starts_at=starts[index],
                        status="scheduled",
                        live_clock=None,
                        venue=None,
                        result_json={},
                        metadata_json={},
                        source_updated_at=None,
                        fetched_at=starts[index],
                    ),
                ]
            )

        session.add_all(fixtures_to_add)
        await session.commit()

        repository = SMS24LiveRepository(session)

        first_page = await repository.list_fixtures(
            sport_slug=sport.slug,
            limit=1,
            offset=0,
        )

        second_page = await repository.list_fixtures(
            sport_slug=sport.slug,
            limit=1,
            offset=1,
        )

        assert len(first_page) == 1
        assert len(second_page) == 1

        assert first_page[0].name == "Canonical Match 1 Primary"
        assert second_page[0].name == "Canonical Match 2 Primary"

        assert first_page[0].id != second_page[0].id

        await session.execute(
            delete(SportsFixture).where(
                SportsFixture.sport_id == sport_id
            )
        )

        await session.execute(
            delete(SportsCanonicalFixture).where(
                SportsCanonicalFixture.sport_id == sport_id
            )
        )

        await session.execute(
            delete(SportsDataSource).where(
                SportsDataSource.id.in_(
                    [primary.id, secondary.id]
                )
            )
        )

        await session.execute(
            delete(Sport).where(
                Sport.id == sport_id
            )
        )

        await session.commit()


@pytest.mark.asyncio
async def test_live_filter_can_select_secondary_live_observation():
    async with SessionFactory() as session:
        sport_id = uuid.uuid4()
        canonical_id = uuid.uuid4()

        sport = Sport(
            id=sport_id,
            slug=f"{PREFIX}live-{uuid.uuid4().hex[:8]}",
            name="SMS24 Live Canonical Test",
            description="Temporary repository live-selection test",
            is_active=True,
        )

        primary = SportsDataSource(
            id=uuid.uuid4(),
            slug=f"{PREFIX}live-primary-{uuid.uuid4().hex[:8]}",
            name="Live Primary",
            provider_type="test",
            priority=10,
            is_active=True,
            health_status="healthy",
        )

        secondary = SportsDataSource(
            id=uuid.uuid4(),
            slug=f"{PREFIX}live-secondary-{uuid.uuid4().hex[:8]}",
            name="Live Secondary",
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
            20,
            0,
            tzinfo=timezone.utc,
        )

        session.add(
            SportsCanonicalFixture(
                id=canonical_id,
                sport_id=sport_id,
                canonical_key=f"sms24:{uuid.uuid4().hex}",
                participant_signature="c" * 64,
                starts_at=starts_at,
            )
        )
        await session.flush()

        primary_scheduled = SportsFixture(
            id=uuid.uuid4(),
            source_id=primary.id,
            sport_id=sport_id,
            competition_id=None,
            canonical_fixture_id=canonical_id,
            external_id="primary-scheduled",
            name="Primary Scheduled Observation",
            starts_at=starts_at,
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
                20,
                1,
                tzinfo=timezone.utc,
            ),
        )

        secondary_live = SportsFixture(
            id=uuid.uuid4(),
            source_id=secondary.id,
            sport_id=sport_id,
            competition_id=None,
            canonical_fixture_id=canonical_id,
            external_id="secondary-live",
            name="Secondary Live Observation",
            starts_at=starts_at,
            status="live",
            live_clock="61'",
            venue=None,
            result_json={"period": "second_half"},
            metadata_json={},
            source_updated_at=None,
            fetched_at=datetime(
                2026,
                9,
                10,
                20,
                2,
                tzinfo=timezone.utc,
            ),
        )

        session.add_all(
            [
                primary_scheduled,
                secondary_live,
            ]
        )
        await session.commit()

        repository = SMS24LiveRepository(session)

        fixtures = await repository.list_fixtures(
            statuses={"live"},
            sport_slug=sport.slug,
            limit=50,
            offset=0,
        )

        assert len(fixtures) == 1

        public_fixture = fixtures[0]

        assert public_fixture.id == secondary_live.id
        assert public_fixture.source_slug == secondary.slug
        assert public_fixture.status == "live"
        assert public_fixture.live_clock == "61'"

        await session.execute(
            delete(SportsFixture).where(
                SportsFixture.sport_id == sport_id
            )
        )

        await session.execute(
            delete(SportsCanonicalFixture).where(
                SportsCanonicalFixture.id == canonical_id
            )
        )

        await session.execute(
            delete(SportsDataSource).where(
                SportsDataSource.id.in_(
                    [primary.id, secondary.id]
                )
            )
        )

        await session.execute(
            delete(Sport).where(
                Sport.id == sport_id
            )
        )

        await session.commit()
