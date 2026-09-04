"""Tests for SMS Performance business rules."""

import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from app.core.exceptions import ForbiddenError
from app.schemas.athlete_performance import (
    AthletePerformanceCreate,
    AthletePerformanceUpdate,
)
from app.services.athlete_performance_service import (
    AthletePerformanceService,
)


USER_ID = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)
OTHER_USER_ID = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)
ATHLETE_ID = uuid.UUID(
    "33333333-3333-3333-3333-333333333333"
)
SPORT_ID = uuid.UUID(
    "44444444-4444-4444-4444-444444444444"
)
PERFORMANCE_ID = uuid.UUID(
    "55555555-5555-5555-5555-555555555555"
)


class FakeSession:
    pass


@pytest.mark.asyncio
async def test_create_performance_uses_athlete_sport_and_declared_status():
    service = AthletePerformanceService(FakeSession())

    athlete = SimpleNamespace(
        id=ATHLETE_ID,
        user_id=USER_ID,
        sport_id=SPORT_ID,
    )

    async def fake_get_by_id(athlete_id):
        assert athlete_id == ATHLETE_ID
        return athlete

    captured = {}

    async def fake_create(performance):
        captured["performance"] = performance
        return performance

    service.athletes.get_by_id = fake_get_by_id
    service.performances.create = fake_create

    data = AthletePerformanceCreate(
        discipline="100 m",
        performance_type="race",
        competition_name="Meeting SMS",
        performance_date=date(2026, 9, 4),
        metrics={
            "time_seconds": 10.42,
            "distance_meters": 100,
        },
        source_url="https://example.com/result",
    )

    result = await service.create_performance(
        ATHLETE_ID,
        data,
        USER_ID,
    )

    assert result.athlete_id == ATHLETE_ID
    assert result.sport_id == SPORT_ID
    assert result.verification_status == "declared"
    assert result.metrics["time_seconds"] == 10.42
    assert result.source_url == (
        "https://example.com/result"
    )


@pytest.mark.asyncio
async def test_non_owner_cannot_create_performance():
    service = AthletePerformanceService(FakeSession())

    athlete = SimpleNamespace(
        id=ATHLETE_ID,
        user_id=OTHER_USER_ID,
        sport_id=SPORT_ID,
    )

    async def fake_get_by_id(athlete_id):
        return athlete

    service.athletes.get_by_id = fake_get_by_id

    data = AthletePerformanceCreate(
        performance_date=date(2026, 9, 4),
        metrics={"goals": 1},
    )

    with pytest.raises(ForbiddenError):
        await service.create_performance(
            ATHLETE_ID,
            data,
            USER_ID,
        )


@pytest.mark.asyncio
async def test_verified_performance_cannot_be_edited_by_athlete():
    service = AthletePerformanceService(FakeSession())

    athlete = SimpleNamespace(
        id=ATHLETE_ID,
        user_id=USER_ID,
        sport_id=SPORT_ID,
    )

    performance = SimpleNamespace(
        id=PERFORMANCE_ID,
        athlete_id=ATHLETE_ID,
        verification_status="verified",
    )

    async def fake_athlete(athlete_id):
        return athlete

    async def fake_performance(performance_id):
        return performance

    service.athletes.get_by_id = fake_athlete
    service.performances.get_by_id = fake_performance

    with pytest.raises(ForbiddenError):
        await service.update_performance(
            ATHLETE_ID,
            PERFORMANCE_ID,
            AthletePerformanceUpdate(
                metrics={"goals": 99}
            ),
            USER_ID,
        )


@pytest.mark.asyncio
async def test_verified_performance_cannot_be_deleted_by_athlete():
    service = AthletePerformanceService(FakeSession())

    athlete = SimpleNamespace(
        id=ATHLETE_ID,
        user_id=USER_ID,
        sport_id=SPORT_ID,
    )

    performance = SimpleNamespace(
        id=PERFORMANCE_ID,
        athlete_id=ATHLETE_ID,
        verification_status="verified",
    )

    async def fake_athlete(athlete_id):
        return athlete

    async def fake_performance(performance_id):
        return performance

    service.athletes.get_by_id = fake_athlete
    service.performances.get_by_id = fake_performance

    with pytest.raises(ForbiddenError):
        await service.delete_performance(
            ATHLETE_ID,
            PERFORMANCE_ID,
            USER_ID,
        )
