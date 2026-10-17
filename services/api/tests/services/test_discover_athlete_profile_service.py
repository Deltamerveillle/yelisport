"""Tests for the public SMS Discover athlete profile service."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.core.exceptions import NotFoundError
from app.services.discover_athlete_profile_service import (
    DiscoverAthleteProfileService,
)
from app.sms24.player_statistics_evidence import (
    AthleteStatisticsEvidence,
    AthleteStatisticsEvidenceResult,
)

ATHLETE_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
SPORT_ID = uuid.uuid4()
PASSPORT_ID = uuid.uuid4()
VIDEO_ID = uuid.uuid4()
OBSERVATION_ID = uuid.uuid4()
SOURCE_ID = uuid.uuid4()
PROVIDER_COMPETITOR_ID = uuid.uuid4()
LINK_ID = uuid.uuid4()
CANONICAL_ID = uuid.uuid4()
NOW = datetime.now(UTC)


def athlete_object():
    return SimpleNamespace(
        id=ATHLETE_ID,
        user_id=USER_ID,
        sport_id=SPORT_ID,
        first_name="Awa",
        last_name="Discover",
        nationality="Ivorian",
        country="Côte d'Ivoire",
        residence_country_id=None,
        city="Abidjan",
        biography="SMS athlete",
        created_at=NOW,
        updated_at=NOW,
    )


def passport_object():
    return SimpleNamespace(
        id=PASSPORT_ID,
        athlete_id=ATHLETE_ID,
        discipline="Football",
        category="Senior",
        position="Forward",
        club_name="SMS FC",
        league_name="SMS League",
        team_name="SMS Team",
        height_cm=None,
        weight_kg=None,
        dominant_side=None,
        available_for_opportunities=True,
        sporting_summary="Attaquante disponible",
        created_at=NOW,
        updated_at=NOW,
    )


class FakeDiscoverRepository:
    def __init__(self, result):
        self.result = result

    async def get_discoverable_by_athlete_id(self, athlete_id):
        assert athlete_id == ATHLETE_ID
        return self.result


class FakePerformanceRepository:
    async def list_by_athlete_id(self, athlete_id):
        assert athlete_id == ATHLETE_ID
        return ()


class FakeStatisticsReader:
    def __init__(self, result):
        self.result = result

    async def read(self, *, athlete_id):
        assert athlete_id == ATHLETE_ID
        return self.result


class FakeVideoRepository:
    async def list_public_by_athlete_id(self, athlete_id):
        assert athlete_id == ATHLETE_ID
        return (
            SimpleNamespace(
                id=VIDEO_ID,
                athlete_id=ATHLETE_ID,
                video_url="https://example.com/public.mp4",
                thumbnail_url=None,
                caption="Public highlight",
                duration_seconds=20,
                publication_status="published",
                moderation_status="approved",
                visibility="public",
                is_active=True,
                view_count=3,
                created_at=NOW,
                updated_at=NOW,
            ),
        )


@pytest.mark.asyncio
async def test_public_profile_strips_internal_statistics_identifiers() -> None:
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

    service = DiscoverAthleteProfileService(
        discover_repository=FakeDiscoverRepository(
            SimpleNamespace(
                athlete=athlete_object(),
                passport=passport_object(),
            )
        ),
        performance_repository=FakePerformanceRepository(),
        statistics_reader=FakeStatisticsReader(evidence),
        video_repository=FakeVideoRepository(),
    )

    profile = await service.get_profile(ATHLETE_ID)
    payload = profile.model_dump(mode="json")

    assert payload["athlete"]["id"] == str(ATHLETE_ID)
    assert "user_id" not in payload["athlete"]

    assert payload["statistics"]["linked"] is True
    assert payload["statistics"]["observations"][0]["scope"] == "season"
    assert payload["statistics"]["observations"][0]["metrics"]["goals"] == 4

    serialized = str(payload)
    for internal_value in (
        USER_ID,
        OBSERVATION_ID,
        SOURCE_ID,
        PROVIDER_COMPETITOR_ID,
        LINK_ID,
        CANONICAL_ID,
    ):
        assert str(internal_value) not in serialized

    assert "athlete_external_id" not in payload["statistics"]["observations"][0]
    assert "metadata" not in payload["statistics"]["observations"][0]

    assert len(payload["videos"]) == 1
    assert payload["videos"][0]["id"] == str(VIDEO_ID)


@pytest.mark.asyncio
async def test_non_discoverable_athlete_is_rejected_before_private_reads() -> None:
    class PerformanceRepositoryMustNotRun:
        async def list_by_athlete_id(self, athlete_id):
            raise AssertionError("performance repository must not run")

    class StatisticsReaderMustNotRun:
        async def read(self, *, athlete_id):
            raise AssertionError("statistics reader must not run")

    class VideoRepositoryMustNotRun:
        async def list_public_by_athlete_id(self, athlete_id):
            raise AssertionError("video repository must not run")

    service = DiscoverAthleteProfileService(
        discover_repository=FakeDiscoverRepository(None),
        performance_repository=PerformanceRepositoryMustNotRun(),
        statistics_reader=StatisticsReaderMustNotRun(),
        video_repository=VideoRepositoryMustNotRun(),
    )

    with pytest.raises(NotFoundError, match="Discover athlete not found"):
        await service.get_profile(ATHLETE_ID)
