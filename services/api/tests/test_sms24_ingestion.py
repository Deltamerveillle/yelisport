"""Tests for the SMS24 ingestion service."""

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest

from app.sms24.ingestion import (
    SMS24IngestionService,
)
from app.sms24.providers import (
    ProviderCompetition,
    ProviderFetchResult,
    ProviderFixture,
    ProviderParticipant,
    SportsDataProvider,
)


NOW = datetime(2026, 9, 6, 22, 30, tzinfo=timezone.utc)

SOURCE_ID = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)
SPORT_ID = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)
COMPETITION_ID = uuid.UUID(
    "33333333-3333-3333-3333-333333333333"
)
FIXTURE_ID = uuid.UUID(
    "44444444-4444-4444-4444-444444444444"
)


class FakeProvider(SportsDataProvider):
    slug = "provider-test"
    name = "Provider Test"

    async def fetch_fixtures(
        self,
        *,
        sport_slug=None,
        starts_from=None,
        starts_until=None,
        live_only=False,
    ):
        raise NotImplementedError

    async def check_health(self):
        raise NotImplementedError


class FakeRepository:
    def __init__(self):
        self.source = SimpleNamespace(
            id=SOURCE_ID,
            slug="provider-test",
            health_status="degraded",
            last_success_at=None,
            last_failure_at=None,
            last_checked_at=None,
        )
        self.sport = SimpleNamespace(
            id=SPORT_ID,
            slug="football",
        )

        self.calls = []
        self.committed = False
        self.rolled_back = False

    async def get_active_source(self, slug):
        self.calls.append(("source", slug))
        if slug == "provider-test":
            return self.source
        return None

    async def get_active_sport(self, slug):
        self.calls.append(("sport", slug))
        if slug == "football":
            return self.sport
        return None

    async def upsert_competition(
        self,
        **kwargs,
    ):
        self.calls.append(
            (
                "competition",
                kwargs["competition"].external_id,
            )
        )
        return SimpleNamespace(id=COMPETITION_ID)

    async def resolve_canonical_fixture(
        self,
        *,
        sport_id,
        candidate,
    ):
        self.calls.append(
            (
                "canonical",
                sport_id,
                candidate.sport_slug,
                tuple(candidate.participants),
                candidate.starts_at,
            )
        )
        return SimpleNamespace(
            id=uuid.UUID(
                "55555555-5555-5555-5555-555555555555"
            )
        )

    async def upsert_fixture(
        self,
        **kwargs,
    ):
        self.calls.append(
            (
                "fixture",
                kwargs["fixture"].external_id,
            )
        )
        return SimpleNamespace(id=FIXTURE_ID)

    async def upsert_competitor(
        self,
        **kwargs,
    ):
        external_id = kwargs["participant"].external_id
        self.calls.append(("competitor", external_id))
        return SimpleNamespace(
            id=uuid.uuid5(
                uuid.NAMESPACE_DNS,
                external_id,
            )
        )

    async def upsert_participant(
        self,
        **kwargs,
    ):
        self.calls.append(
            (
                "participant",
                kwargs["participant"].external_id,
            )
        )
        return SimpleNamespace(id=uuid.uuid4())

    async def mark_source_success(
        self,
        source,
        *,
        checked_at,
    ):
        source.health_status = "healthy"
        source.last_success_at = checked_at
        source.last_checked_at = checked_at
        self.calls.append(("success", checked_at))

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


def make_result():
    return ProviderFetchResult(
        fetched_at=NOW,
        raw_count=1,
        fixtures=[
            ProviderFixture(
                external_id="fixture-001",
                sport_slug="football",
                starts_at=NOW,
                status="live",
                name="Abidjan - Dakar",
                live_clock="55'",
                competition=ProviderCompetition(
                    external_id="competition-001",
                    name="SMS Africa League",
                    country_code="CI",
                    season="2026",
                ),
                participants=[
                    ProviderParticipant(
                        external_id="team-abidjan",
                        name="Abidjan",
                        role="home",
                        position=0,
                        score={"score": 2},
                    ),
                    ProviderParticipant(
                        external_id="team-dakar",
                        name="Dakar",
                        role="away",
                        position=1,
                        score={"score": 1},
                    ),
                ],
                result={
                    "period": "second_half",
                },
            )
        ],
    )


@pytest.mark.asyncio
async def test_ingestion_processes_normalized_fixture():
    repository = FakeRepository()
    service = SMS24IngestionService(repository)

    stats = await service.ingest_provider_result(
        provider=FakeProvider(),
        result=make_result(),
    )

    assert stats.provider_slug == "provider-test"
    assert stats.fixtures_processed == 1
    assert stats.competitions_processed == 1
    assert stats.competitors_processed == 2
    assert stats.participants_processed == 2

    assert repository.committed is True
    assert repository.rolled_back is False
    assert repository.source.health_status == "healthy"
    assert repository.source.last_success_at == NOW

    assert ("fixture", "fixture-001") in repository.calls
    assert ("competitor", "team-abidjan") in repository.calls
    assert ("competitor", "team-dakar") in repository.calls


@pytest.mark.asyncio
async def test_ingestion_ignores_duplicate_participant_in_same_fixture():
    repository = FakeRepository()
    service = SMS24IngestionService(repository)

    result = make_result()
    duplicate = ProviderParticipant(
        external_id="team-abidjan",
        name="Abidjan duplicate",
        position=2,
    )
    result.fixtures[0].participants.append(duplicate)

    stats = await service.ingest_provider_result(
        provider=FakeProvider(),
        result=result,
    )

    assert stats.competitors_processed == 2
    assert stats.participants_processed == 2


@pytest.mark.asyncio
async def test_ingestion_rejects_unknown_sport_and_rolls_back():
    repository = FakeRepository()
    service = SMS24IngestionService(repository)

    result = make_result()
    result.fixtures[0].sport_slug = "unknown-sport"

    with pytest.raises(
        ValueError,
        match="Unknown or inactive sport",
    ):
        await service.ingest_provider_result(
            provider=FakeProvider(),
            result=result,
        )

    assert repository.committed is False
    assert repository.rolled_back is True


@pytest.mark.asyncio
async def test_ingestion_rejects_invalid_fixture_status():
    repository = FakeRepository()
    service = SMS24IngestionService(repository)

    result = make_result()
    result.fixtures[0].status = "playing"

    with pytest.raises(
        ValueError,
        match="Unsupported SMS24 fixture status",
    ):
        await service.ingest_provider_result(
            provider=FakeProvider(),
            result=result,
        )

    assert repository.rolled_back is True


@pytest.mark.asyncio
async def test_ingestion_rejects_naive_fixture_datetime():
    repository = FakeRepository()
    service = SMS24IngestionService(repository)

    result = make_result()
    result.fixtures[0].starts_at = datetime(
        2026,
        9,
        6,
        22,
        30,
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        await service.ingest_provider_result(
            provider=FakeProvider(),
            result=result,
        )

    assert repository.rolled_back is True


CANONICAL_FIXTURE_ID = uuid.UUID(
    "55555555-5555-5555-5555-555555555555"
)


class CanonicalFakeRepository(FakeRepository):
    async def resolve_canonical_fixture(
        self,
        *,
        sport_id,
        candidate,
    ):
        self.calls.append(
            (
                "canonical",
                sport_id,
                candidate.sport_slug,
                tuple(candidate.participants),
                candidate.starts_at,
            )
        )
        return SimpleNamespace(
            id=CANONICAL_FIXTURE_ID,
        )

    async def upsert_fixture(
        self,
        **kwargs,
    ):
        self.calls.append(
            (
                "fixture_with_canonical",
                kwargs["fixture"].external_id,
                kwargs["canonical_fixture_id"],
            )
        )
        return SimpleNamespace(id=FIXTURE_ID)


@pytest.mark.asyncio
async def test_ingestion_attaches_provider_fixture_to_canonical_fixture():
    repository = CanonicalFakeRepository()
    service = SMS24IngestionService(repository)

    await service.ingest_provider_result(
        provider=FakeProvider(),
        result=make_result(),
    )

    assert (
        "canonical",
        SPORT_ID,
        "football",
        ("Abidjan", "Dakar"),
        NOW,
    ) in repository.calls

    assert (
        "fixture_with_canonical",
        "fixture-001",
        CANONICAL_FIXTURE_ID,
    ) in repository.calls
