import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.moderation_report import ModerationReport
from app.services.discover_video_service import DiscoverVideoService
from app.services.moderation_service import ModerationService


@pytest.mark.asyncio
async def test_create_publication_review_creates_open_case() -> None:
    service = ModerationService(AsyncMock())

    owner_id = uuid.uuid4()
    video_id = uuid.uuid4()

    service.reports.get_open_publication_review = AsyncMock(
        return_value=None
    )

    async def create_report(report: ModerationReport) -> ModerationReport:
        report.id = uuid.uuid4()
        return report

    service.reports.create = AsyncMock(
        side_effect=create_report
    )
    service.events.create = AsyncMock(
        side_effect=lambda event: event
    )

    report = await service.create_publication_review(
        owner_user_id=owner_id,
        video_id=video_id,
    )

    assert report.reporter_user_id == owner_id
    assert report.resource_type == "discover_video"
    assert report.resource_id == video_id
    assert report.origin == "publication_review"
    assert report.status == "submitted"

    service.reports.create.assert_awaited_once()
    service.events.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_publication_review_reuses_existing_open_case() -> None:
    service = ModerationService(AsyncMock())

    existing = SimpleNamespace(
        id=uuid.uuid4(),
        origin="publication_review",
        status="submitted",
    )

    service.reports.get_open_publication_review = AsyncMock(
        return_value=existing
    )
    service.reports.create = AsyncMock()
    service.events.create = AsyncMock()

    result = await service.create_publication_review(
        owner_user_id=uuid.uuid4(),
        video_id=uuid.uuid4(),
    )

    assert result is existing
    service.reports.create.assert_not_awaited()
    service.events.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_publication_enqueues_moderation_review() -> None:
    service = DiscoverVideoService(AsyncMock())

    owner_id = uuid.uuid4()
    athlete_id = uuid.uuid4()
    video_id = uuid.uuid4()

    video = SimpleNamespace(
        id=video_id,
        athlete_id=athlete_id,
        is_active=True,
        publication_status="draft",
        moderation_status="pending",
    )

    service._get_owned_video = AsyncMock(
        return_value=video
    )
    service.videos.update = AsyncMock(
        side_effect=lambda item: item
    )
    service.moderation.create_publication_review = AsyncMock()

    result = await service.request_publication(
        athlete_id,
        video_id,
        owner_id,
    )

    assert result.publication_status == "published"
    assert result.moderation_status == "pending"

    service.moderation.create_publication_review.assert_awaited_once_with(
        owner_user_id=owner_id,
        video_id=video_id,
    )
