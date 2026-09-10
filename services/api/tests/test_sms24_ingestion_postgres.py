"""Real PostgreSQL UPSERT integration tests for SMS24 ingestion."""

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models.sport import Sport
from app.models.sports_live import (
    SportsCanonicalFixture,
    SportsCompetition,
    SportsCompetitor,
    SportsDataSource,
    SportsFixture,
    SportsFixtureParticipant,
)
from app.sms24.canonical import (
    CanonicalFixtureCandidate,
)
from app.sms24.ingestion import SMS24IngestionRepository
from app.sms24.providers.base import (
    ProviderCompetition,
    ProviderFixture,
    ProviderParticipant,
)


PREFIX = "sms24-upsert-pg-"

_test_engine = create_async_engine(
    get_settings().database_url,
    poolclass=NullPool,
)

TestSessionFactory = async_sessionmaker(
    _test_engine,
    expire_on_commit=False,
)


async def cleanup(session, source_id):
    fixture_ids = select(SportsFixture.id).where(
        SportsFixture.source_id == source_id
    )

    await session.execute(
        delete(SportsFixtureParticipant).where(
            SportsFixtureParticipant.fixture_id.in_(fixture_ids)
        )
    )

    await session.execute(
        delete(SportsFixture).where(
            SportsFixture.source_id == source_id
        )
    )

    await session.execute(
        delete(SportsCompetitor).where(
            SportsCompetitor.source_id == source_id
        )
    )

    await session.execute(
        delete(SportsCompetition).where(
            SportsCompetition.source_id == source_id
        )
    )

    await session.execute(
        delete(SportsDataSource).where(
            SportsDataSource.id == source_id
        )
    )

    await session.commit()


@pytest.mark.asyncio
async def test_real_postgres_sms24_upserts_are_idempotent():
    async with TestSessionFactory() as session:
        sport_id = uuid.uuid4()
        sport_slug = f"{PREFIX}sport-{uuid.uuid4().hex[:12]}"

        sport = Sport(
            id=sport_id,
            slug=sport_slug,
            name="SMS24 PostgreSQL Test Sport",
            description="Temporary integration-test sport",
            is_active=True,
        )

        session.add(sport)
        await session.commit()

        source_id = uuid.uuid4()
        source_slug = f"{PREFIX}{uuid.uuid4().hex[:12]}"

        source = SportsDataSource(
            id=source_id,
            slug=source_slug,
            name="SMS24 PostgreSQL UPSERT Test",
            provider_type="test",
            priority=999,
            is_active=True,
            health_status="healthy",
        )

        session.add(source)
        await session.commit()

        repository = SMS24IngestionRepository(session)

        first_fetch = datetime(
            2026,
            9,
            6,
            20,
            0,
            tzinfo=timezone.utc,
        )

        second_fetch = datetime(
            2026,
            9,
            6,
            20,
            5,
            tzinfo=timezone.utc,
        )

        competition_v1 = ProviderCompetition(
            external_id="competition-001",
            name="Competition V1",
            country_code="CI",
            season="2026",
        )

        competition_v2 = ProviderCompetition(
            external_id="competition-001",
            name="Competition V2",
            country_code="CI",
            season="2026-2027",
        )

        competition_first = await repository.upsert_competition(
            source_id=source_id,
            sport_id=sport.id,
            competition=competition_v1,
            fetched_at=first_fetch,
        )

        competition_second = await repository.upsert_competition(
            source_id=source_id,
            sport_id=sport.id,
            competition=competition_v2,
            fetched_at=second_fetch,
        )

        assert competition_first.id == competition_second.id

        participant_v1 = ProviderParticipant(
            external_id="competitor-001",
            name="Competitor V1",
            competitor_type="team",
            position=0,
            role="home",
            score={"value": 1},
            result_status=None,
        )

        participant_v2 = ProviderParticipant(
            external_id="competitor-001",
            name="Competitor V2",
            competitor_type="team",
            position=0,
            role="home",
            score={"value": 2},
            result_status="winner",
        )

        competitor_first = await repository.upsert_competitor(
            source_id=source_id,
            sport_id=sport.id,
            participant=participant_v1,
            fetched_at=first_fetch,
        )

        competitor_second = await repository.upsert_competitor(
            source_id=source_id,
            sport_id=sport.id,
            participant=participant_v2,
            fetched_at=second_fetch,
        )

        assert competitor_first.id == competitor_second.id

        fixture_v1 = ProviderFixture(
            external_id="fixture-001",
            sport_slug=sport.slug,
            starts_at=datetime(
                2026,
                9,
                7,
                18,
                0,
                tzinfo=timezone.utc,
            ),
            status="scheduled",
            name="Fixture V1",
            live_clock=None,
            venue="Venue V1",
            competition=competition_v1,
            participants=[participant_v1],
            result={},
            metadata={"version": 1},
        )

        fixture_v2 = ProviderFixture(
            external_id="fixture-001",
            sport_slug=sport.slug,
            starts_at=datetime(
                2026,
                9,
                7,
                18,
                0,
                tzinfo=timezone.utc,
            ),
            status="live",
            name="Fixture V2",
            live_clock="67",
            venue="Venue V2",
            competition=competition_v2,
            participants=[participant_v2],
            result={"home": 2, "away": 1},
            metadata={"version": 2},
        )

        canonical_candidate = CanonicalFixtureCandidate(
            sport_slug=sport.slug,
            starts_at=fixture_v1.starts_at,
            participants=[
                "Competitor V1",
                "Opponent Test",
            ],
        )

        canonical_fixture = (
            await repository.resolve_canonical_fixture(
                sport_id=sport.id,
                candidate=canonical_candidate,
            )
        )

        fixture_first = await repository.upsert_fixture(
            source_id=source_id,
            sport_id=sport.id,
            competition_id=competition_first.id,
            canonical_fixture_id=canonical_fixture.id,
            fixture=fixture_v1,
            fetched_at=first_fetch,
        )

        fixture_second = await repository.upsert_fixture(
            source_id=source_id,
            sport_id=sport.id,
            competition_id=competition_second.id,
            canonical_fixture_id=canonical_fixture.id,
            fixture=fixture_v2,
            fetched_at=second_fetch,
        )

        assert fixture_first.id == fixture_second.id

        fixture_participant_first = (
            await repository.upsert_participant(
                fixture_id=fixture_first.id,
                competitor_id=competitor_first.id,
                participant=participant_v1,
            )
        )

        fixture_participant_second = (
            await repository.upsert_participant(
                fixture_id=fixture_second.id,
                competitor_id=competitor_second.id,
                participant=participant_v2,
            )
        )

        assert (
            fixture_participant_first.id
            == fixture_participant_second.id
        )

        await repository.commit()

        competition_count = await session.scalar(
            select(func.count())
            .select_from(SportsCompetition)
            .where(
                SportsCompetition.source_id == source_id,
                SportsCompetition.external_id == "competition-001",
            )
        )

        competitor_count = await session.scalar(
            select(func.count())
            .select_from(SportsCompetitor)
            .where(
                SportsCompetitor.source_id == source_id,
                SportsCompetitor.external_id == "competitor-001",
            )
        )

        fixture_count = await session.scalar(
            select(func.count())
            .select_from(SportsFixture)
            .where(
                SportsFixture.source_id == source_id,
                SportsFixture.external_id == "fixture-001",
            )
        )

        fixture_participant_count = await session.scalar(
            select(func.count())
            .select_from(SportsFixtureParticipant)
            .where(
                SportsFixtureParticipant.fixture_id
                == fixture_second.id,
                SportsFixtureParticipant.competitor_id
                == competitor_second.id,
            )
        )

        assert competition_count == 1
        assert competitor_count == 1
        assert fixture_count == 1
        assert fixture_participant_count == 1

        refreshed_competition = await session.scalar(
            select(SportsCompetition)
            .where(
                SportsCompetition.id == competition_second.id
            )
            .execution_options(populate_existing=True)
        )

        refreshed_competitor = await session.scalar(
            select(SportsCompetitor)
            .where(
                SportsCompetitor.id == competitor_second.id
            )
            .execution_options(populate_existing=True)
        )

        refreshed_fixture = await session.scalar(
            select(SportsFixture)
            .where(
                SportsFixture.id == fixture_second.id
            )
            .execution_options(populate_existing=True)
        )

        refreshed_participant = await session.scalar(
            select(SportsFixtureParticipant)
            .where(
                SportsFixtureParticipant.id
                == fixture_participant_second.id
            )
            .execution_options(populate_existing=True)
        )

        assert refreshed_competition.name == "Competition V2"
        assert refreshed_competition.season == "2026-2027"

        assert refreshed_competitor.name == "Competitor V2"

        assert refreshed_fixture.name == "Fixture V2"
        assert refreshed_fixture.status == "live"
        assert refreshed_fixture.live_clock == "67"
        assert refreshed_fixture.venue == "Venue V2"
        assert refreshed_fixture.result_json == {
            "home": 2,
            "away": 1,
        }
        assert refreshed_fixture.metadata_json == {
            "version": 2,
        }

        assert refreshed_participant.score_json == {
            "value": 2,
        }
        assert refreshed_participant.result_status == "winner"

        await cleanup(session, source_id)

        await session.execute(
            delete(SportsCanonicalFixture).where(
                SportsCanonicalFixture.sport_id == sport_id
            )
        )

        await session.execute(
            delete(Sport).where(Sport.id == sport_id)
        )
        await session.commit()



@pytest.mark.asyncio
async def test_real_postgres_cross_provider_fixtures_share_one_canonical():
    async with TestSessionFactory() as session:
        sport_id = uuid.uuid4()
        sport_slug = (
            f"{PREFIX}canonical-sport-{uuid.uuid4().hex[:10]}"
        )

        sport = Sport(
            id=sport_id,
            slug=sport_slug,
            name="SMS24 Canonical Cross Provider Test",
            description="Temporary canonical integration-test sport",
            is_active=True,
        )
        session.add(sport)

        source_a = SportsDataSource(
            id=uuid.uuid4(),
            slug=f"{PREFIX}provider-a-{uuid.uuid4().hex[:8]}",
            name="Canonical Provider A",
            provider_type="test",
            priority=901,
            is_active=True,
            health_status="healthy",
        )

        source_b = SportsDataSource(
            id=uuid.uuid4(),
            slug=f"{PREFIX}provider-b-{uuid.uuid4().hex[:8]}",
            name="Canonical Provider B",
            provider_type="test",
            priority=902,
            is_active=True,
            health_status="healthy",
        )

        session.add_all([source_a, source_b])
        await session.commit()

        repository = SMS24IngestionRepository(session)

        first_start = datetime(
            2026,
            9,
            10,
            18,
            0,
            tzinfo=timezone.utc,
        )

        second_start = datetime(
            2026,
            9,
            10,
            18,
            3,
            tzinfo=timezone.utc,
        )

        candidate_a = CanonicalFixtureCandidate(
            sport_slug=sport_slug,
            starts_at=first_start,
            participants=[
                "ASEC Mimosas",
                "Stade d'Abidjan",
            ],
            competition_name="Ligue 1 Côte d'Ivoire",
        )

        candidate_b = CanonicalFixtureCandidate(
            sport_slug=sport_slug,
            starts_at=second_start,
            participants=[
                "STADE D ABIDJAN",
                "  asec   mimosas ",
            ],
            competition_name="Ivory Coast Ligue 1",
        )

        canonical_a = await repository.resolve_canonical_fixture(
            sport_id=sport_id,
            candidate=candidate_a,
        )

        canonical_b = await repository.resolve_canonical_fixture(
            sport_id=sport_id,
            candidate=candidate_b,
        )

        assert canonical_a.id == canonical_b.id

        fixture_a = ProviderFixture(
            external_id="provider-a-fixture-100",
            sport_slug=sport_slug,
            starts_at=first_start,
            status="scheduled",
            name="ASEC Mimosas vs Stade d'Abidjan",
            participants=[],
            result={},
            metadata={"provider": "a"},
        )

        fixture_b = ProviderFixture(
            external_id="provider-b-fixture-900",
            sport_slug=sport_slug,
            starts_at=second_start,
            status="scheduled",
            name="Stade d'Abidjan - ASEC Mimosas",
            participants=[],
            result={},
            metadata={"provider": "b"},
        )

        stored_a = await repository.upsert_fixture(
            source_id=source_a.id,
            sport_id=sport_id,
            competition_id=None,
            canonical_fixture_id=canonical_a.id,
            fixture=fixture_a,
            fetched_at=first_start,
        )

        stored_b = await repository.upsert_fixture(
            source_id=source_b.id,
            sport_id=sport_id,
            competition_id=None,
            canonical_fixture_id=canonical_b.id,
            fixture=fixture_b,
            fetched_at=second_start,
        )

        await repository.commit()

        # Provider observations must remain distinct.
        assert stored_a.id != stored_b.id

        provider_fixture_count = await session.scalar(
            select(func.count())
            .select_from(SportsFixture)
            .where(
                SportsFixture.canonical_fixture_id
                == canonical_a.id
            )
        )

        canonical_count = await session.scalar(
            select(func.count())
            .select_from(SportsCanonicalFixture)
            .where(
                SportsCanonicalFixture.id == canonical_a.id
            )
        )

        distinct_source_count = await session.scalar(
            select(
                func.count(
                    func.distinct(SportsFixture.source_id)
                )
            )
            .where(
                SportsFixture.canonical_fixture_id
                == canonical_a.id
            )
        )

        assert provider_fixture_count == 2
        assert canonical_count == 1
        assert distinct_source_count == 2

        refreshed_a = await session.scalar(
            select(SportsFixture).where(
                SportsFixture.id == stored_a.id
            )
        )

        refreshed_b = await session.scalar(
            select(SportsFixture).where(
                SportsFixture.id == stored_b.id
            )
        )

        assert (
            refreshed_a.canonical_fixture_id
            == refreshed_b.canonical_fixture_id
            == canonical_a.id
        )

        # Clean up in FK-safe order.
        await cleanup(session, source_a.id)
        await cleanup(session, source_b.id)

        await session.execute(
            delete(SportsCanonicalFixture).where(
                SportsCanonicalFixture.id == canonical_a.id
            )
        )

        await session.execute(
            delete(Sport).where(Sport.id == sport_id)
        )

        await session.commit()
