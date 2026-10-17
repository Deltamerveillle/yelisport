"""Tests for the read-only enriched athlete profile projection."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.core.exceptions import NotFoundError
from app.services.athlete_profile_service import AthleteProfileService
from app.sms24.player_statistics_evidence import (
    AthleteStatisticsEvidence,
    AthleteStatisticsEvidenceResult,
)

ATHLETE_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
SPORT_ID = uuid.uuid4()
LINK_ID = uuid.uuid4()
CANONICAL_ID = uuid.uuid4()
OBSERVATION_ID = uuid.uuid4()
SOURCE_ID = uuid.uuid4()
PROVIDER_COMPETITOR_ID = uuid.uuid4()
NOW = datetime.now(UTC)


def athlete_object():
    return SimpleNamespace(
        id=ATHLETE_ID,
        user_id=USER_ID,
        sport_id=SPORT_ID,
        first_name="Dramane",
        last_name="Fofana",
        nationality="Ivoirienne",
        country="Côte d'Ivoire",
        residence_country_id=None,
        city="Abidjan",
        biography="Profil sportif SMS",
        created_at=NOW,
        updated_at=NOW,
    )


class FakeAthleteRepository:
    def __init__(self, athlete):
        self.athlete = athlete

    async def get_by_id(self, athlete_id):
        assert athlete_id == ATHLETE_ID
        return self.athlete


class FakePerformanceRepository:
    def __init__(self, performances=()):
        self.performances = performances

    async def list_by_athlete_id(self, athlete_id):
        assert athlete_id == ATHLETE_ID
        return self.performances


class FakeStatisticsReader:
    def __init__(self, result):
        self.result = result

    async def read(self, *, athlete_id):
        assert athlete_id == ATHLETE_ID
        return self.result


@pytest.mark.asyncio
async def test_unlinked_athlete_profile_has_no_provider_statistics() -> None:
    evidence = AthleteStatisticsEvidenceResult(
        athlete_id=ATHLETE_ID,
        identity_link_id=None,
        identity_status=None,
        identity_method=None,
        canonical_competitor_id=None,
    )
    service = AthleteProfileService(
        athlete_repository=FakeAthleteRepository(athlete_object()),
        performance_repository=FakePerformanceRepository(),
        statistics_reader=FakeStatisticsReader(evidence),
    )

    profile = await service.get_profile(ATHLETE_ID)

    assert profile.athlete.id == ATHLETE_ID
    assert profile.performances == []
    assert profile.statistics.identity.linked is False
    assert profile.statistics.identity.identity_link_id is None
    assert profile.statistics.observations == []


@pytest.mark.asyncio
async def test_linked_athlete_profile_exposes_provider_evidence() -> None:
    observation = AthleteStatisticsEvidence(
        observation_id=OBSERVATION_ID,
        source_id=SOURCE_ID,
        sport_id=SPORT_ID,
        provider_competitor_id=PROVIDER_COMPETITOR_ID,
        athlete_external_id="758",
        scope="season",
        period_label="2026",
        metrics={"appearances": 12, "goals": 4},
        metadata={"provider": "sportmonks"},
        fetched_at=NOW,
        source_updated_at=None,
    )
    evidence = AthleteStatisticsEvidenceResult(
        athlete_id=ATHLETE_ID,
        identity_link_id=LINK_ID,
        identity_status="declared",
        identity_method="athlete_claim",
        canonical_competitor_id=CANONICAL_ID,
        observations=(observation,),
    )
    service = AthleteProfileService(
        athlete_repository=FakeAthleteRepository(athlete_object()),
        performance_repository=FakePerformanceRepository(),
        statistics_reader=FakeStatisticsReader(evidence),
    )

    profile = await service.get_profile(ATHLETE_ID)

    assert profile.statistics.identity.linked is True
    assert profile.statistics.identity.identity_link_id == LINK_ID
    assert profile.statistics.identity.status == "declared"
    assert profile.statistics.identity.method == "athlete_claim"
    assert profile.statistics.identity.canonical_competitor_id == CANONICAL_ID
    assert len(profile.statistics.observations) == 1
    assert profile.statistics.observations[0].observation_id == OBSERVATION_ID
    assert profile.statistics.observations[0].athlete_external_id == "758"
    assert profile.statistics.observations[0].metrics["goals"] == 4


@pytest.mark.asyncio
async def test_missing_athlete_is_rejected_before_statistics_lookup() -> None:
    class PerformanceRepositoryMustNotRun:
        async def list_by_athlete_id(self, athlete_id):
            raise AssertionError("performance repository must not run")

    class ReaderMustNotRun:
        async def read(self, *, athlete_id):
            raise AssertionError("statistics reader must not run")

    service = AthleteProfileService(
        athlete_repository=FakeAthleteRepository(None),
        performance_repository=PerformanceRepositoryMustNotRun(),
        statistics_reader=ReaderMustNotRun(),
    )

    with pytest.raises(NotFoundError, match="Athlete not found"):
        await service.get_profile(ATHLETE_ID)


@pytest.mark.asyncio
async def test_athlete_profile_exposes_human_performance_separately() -> None:
    performance_id = uuid.uuid4()
    performance = SimpleNamespace(
        id=performance_id,
        athlete_id=ATHLETE_ID,
        sport_id=SPORT_ID,
        discipline="football",
        performance_type="match",
        competition_name="SMS Test Competition",
        season="2026",
        performance_date=NOW.date(),
        metrics={"goals": 2, "assists": 1},
        summary="Performance documentée",
        verification_status="documented",
        source_name="SMS",
        source_url=None,
        created_at=NOW,
        updated_at=NOW,
    )
    evidence = AthleteStatisticsEvidenceResult(
        athlete_id=ATHLETE_ID,
        identity_link_id=None,
        identity_status=None,
        identity_method=None,
        canonical_competitor_id=None,
    )
    service = AthleteProfileService(
        athlete_repository=FakeAthleteRepository(athlete_object()),
        performance_repository=FakePerformanceRepository((performance,)),
        statistics_reader=FakeStatisticsReader(evidence),
    )

    profile = await service.get_profile(ATHLETE_ID)

    assert len(profile.performances) == 1
    assert profile.performances[0].id == performance_id
    assert profile.performances[0].athlete_id == ATHLETE_ID
    assert profile.performances[0].verification_status == "documented"
    assert profile.performances[0].metrics["goals"] == 2
    assert profile.statistics.identity.linked is False
    assert profile.statistics.observations == []
