"""Business-rule tests for SMS Discover."""

import uuid
from types import SimpleNamespace

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.schemas.discover_video import (
    DiscoverVideoCreate,
    DiscoverVideoUpdate,
)
from app.services.discover_video_service import DiscoverVideoService


USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
ATHLETE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
OTHER_ATHLETE_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")
VIDEO_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


class FakeAthleteRepository:
    def __init__(self, athletes=None):
        self.athletes = athletes or {}

    async def get_by_id(self, athlete_id):
        return self.athletes.get(athlete_id)


class FakeVideoRepository:
    def __init__(self, videos=None):
        self.videos = videos or {}
        self.created = None
        self.updated = None
        self.deleted = None
        self.public_args = None

    async def create(self, video):
        self.created = video
        video.id = VIDEO_ID
        return video

    async def get_by_id(self, video_id):
        return self.videos.get(video_id)

    async def list_by_athlete_id(self, athlete_id):
        return [
            video
            for video in self.videos.values()
            if video.athlete_id == athlete_id
        ]

    async def list_public_discover(self, limit=50, offset=0):
        self.public_args = (limit, offset)
        return [
            video
            for video in self.videos.values()
            if (
                video.publication_status == "published"
                and video.moderation_status == "approved"
                and video.visibility == "public"
                and video.is_active is True
            )
        ][offset:offset + limit]

    async def update(self, video):
        self.updated = video
        return video

    async def delete(self, video):
        self.deleted = video


def athlete(
    athlete_id=ATHLETE_ID,
    user_id=USER_ID,
):
    return SimpleNamespace(
        id=athlete_id,
        user_id=user_id,
    )


def video(
    video_id=VIDEO_ID,
    athlete_id=ATHLETE_ID,
    **overrides,
):
    values = {
        "id": video_id,
        "athlete_id": athlete_id,
        "video_url": "https://example.com/video.mp4",
        "thumbnail_url": None,
        "caption": "Talent",
        "duration_seconds": 20,
        "publication_status": "draft",
        "moderation_status": "pending",
        "visibility": "public",
        "is_active": True,
        "view_count": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_service(
    athletes=None,
    videos=None,
):
    service = DiscoverVideoService.__new__(DiscoverVideoService)
    service.athletes = FakeAthleteRepository(athletes)
    service.videos = FakeVideoRepository(videos)
    return service


@pytest.mark.asyncio
async def test_create_forces_safe_initial_statuses():
    service = make_service(
        athletes={
            ATHLETE_ID: athlete(),
        }
    )

    data = DiscoverVideoCreate(
        video_url="https://example.com/video.mp4",
        duration_seconds=20,
        visibility="public",
    )

    result = await service.create_video(
        ATHLETE_ID,
        data,
        USER_ID,
    )

    assert result.athlete_id == ATHLETE_ID
    assert result.publication_status == "draft"
    assert result.moderation_status == "pending"
    assert result.is_active is True
    assert result.view_count == 0


@pytest.mark.asyncio
async def test_create_forbidden_for_non_owner():
    service = make_service(
        athletes={
            ATHLETE_ID: athlete(
                user_id=OTHER_USER_ID
            ),
        }
    )

    data = DiscoverVideoCreate(
        video_url="https://example.com/video.mp4",
        duration_seconds=20,
    )

    with pytest.raises(ForbiddenError):
        await service.create_video(
            ATHLETE_ID,
            data,
            USER_ID,
        )


@pytest.mark.asyncio
async def test_missing_athlete_returns_not_found():
    service = make_service()

    data = DiscoverVideoCreate(
        video_url="https://example.com/video.mp4",
        duration_seconds=20,
    )

    with pytest.raises(NotFoundError):
        await service.create_video(
            ATHLETE_ID,
            data,
            USER_ID,
        )


@pytest.mark.asyncio
async def test_get_rejects_video_from_another_athlete():
    service = make_service(
        athletes={
            ATHLETE_ID: athlete(),
        },
        videos={
            VIDEO_ID: video(
                athlete_id=OTHER_ATHLETE_ID
            ),
        },
    )

    with pytest.raises(NotFoundError):
        await service.get_video(
            ATHLETE_ID,
            VIDEO_ID,
            USER_ID,
        )


@pytest.mark.asyncio
async def test_list_forbidden_for_non_owner():
    service = make_service(
        athletes={
            ATHLETE_ID: athlete(
                user_id=OTHER_USER_ID
            ),
        }
    )

    with pytest.raises(ForbiddenError):
        await service.list_athlete_videos(
            ATHLETE_ID,
            USER_ID,
        )


@pytest.mark.asyncio
async def test_update_changes_only_allowed_payload_fields():
    existing = video(
        caption="Before",
        duration_seconds=20,
    )

    service = make_service(
        athletes={
            ATHLETE_ID: athlete(),
        },
        videos={
            VIDEO_ID: existing,
        },
    )

    data = DiscoverVideoUpdate(
        caption="After",
        duration_seconds=25,
    )

    result = await service.update_video(
        ATHLETE_ID,
        VIDEO_ID,
        data,
        USER_ID,
    )

    assert result.caption == "After"
    assert result.duration_seconds == 25

    assert result.publication_status == "draft"
    assert result.moderation_status == "pending"
    assert result.view_count == 0
    assert result.is_active is True


@pytest.mark.asyncio
async def test_delete_owned_video():
    existing = video()

    service = make_service(
        athletes={
            ATHLETE_ID: athlete(),
        },
        videos={
            VIDEO_ID: existing,
        },
    )

    await service.delete_video(
        ATHLETE_ID,
        VIDEO_ID,
        USER_ID,
    )

    assert service.videos.deleted is existing


@pytest.mark.asyncio
async def test_public_feed_keeps_only_publishable_videos():
    good = video(
        video_id=uuid.uuid4(),
        publication_status="published",
        moderation_status="approved",
        visibility="public",
        is_active=True,
    )

    draft = video(
        video_id=uuid.uuid4(),
        publication_status="draft",
        moderation_status="approved",
    )

    rejected = video(
        video_id=uuid.uuid4(),
        publication_status="published",
        moderation_status="rejected",
    )

    private = video(
        video_id=uuid.uuid4(),
        publication_status="published",
        moderation_status="approved",
        visibility="private",
    )

    inactive = video(
        video_id=uuid.uuid4(),
        publication_status="published",
        moderation_status="approved",
        is_active=False,
    )

    videos = {
        item.id: item
        for item in (
            good,
            draft,
            rejected,
            private,
            inactive,
        )
    }

    service = make_service(videos=videos)

    result = await service.list_public_discover(
        limit=50,
        offset=0,
    )

    assert result == [good]
    assert service.videos.public_args == (50, 0)


@pytest.mark.asyncio
async def test_request_publication_moves_video_to_published_pending():
    existing = video(
        publication_status="draft",
        moderation_status="pending",
    )

    service = make_service(
        athletes={
            ATHLETE_ID: athlete(),
        },
        videos={
            VIDEO_ID: existing,
        },
    )

    result = await service.request_publication(
        ATHLETE_ID,
        VIDEO_ID,
        USER_ID,
    )

    assert result.publication_status == "published"
    assert result.moderation_status == "pending"


@pytest.mark.asyncio
async def test_request_publication_resubmits_rejected_video():
    existing = video(
        publication_status="published",
        moderation_status="rejected",
    )

    service = make_service(
        athletes={
            ATHLETE_ID: athlete(),
        },
        videos={
            VIDEO_ID: existing,
        },
    )

    result = await service.request_publication(
        ATHLETE_ID,
        VIDEO_ID,
        USER_ID,
    )

    assert result.publication_status == "published"
    assert result.moderation_status == "pending"


@pytest.mark.asyncio
async def test_approved_video_edit_resets_moderation_to_pending():
    existing = video(
        caption="Original",
        publication_status="published",
        moderation_status="approved",
    )

    service = make_service(
        athletes={
            ATHLETE_ID: athlete(),
        },
        videos={
            VIDEO_ID: existing,
        },
    )

    result = await service.update_video(
        ATHLETE_ID,
        VIDEO_ID,
        DiscoverVideoUpdate(
            caption="Nouvelle version",
        ),
        USER_ID,
    )

    assert result.caption == "Nouvelle version"
    assert result.publication_status == "published"
    assert result.moderation_status == "pending"


@pytest.mark.asyncio
async def test_approved_video_unchanged_value_keeps_approval():
    existing = video(
        caption="Même texte",
        publication_status="published",
        moderation_status="approved",
    )

    service = make_service(
        athletes={
            ATHLETE_ID: athlete(),
        },
        videos={
            VIDEO_ID: existing,
        },
    )

    result = await service.update_video(
        ATHLETE_ID,
        VIDEO_ID,
        DiscoverVideoUpdate(
            caption="Même texte",
        ),
        USER_ID,
    )

    assert result.moderation_status == "approved"
