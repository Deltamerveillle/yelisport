"""Service layer for SMS Discover videos."""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.discover_video import DiscoverVideo
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.discover_video_repository import DiscoverVideoRepository
from app.schemas.discover_video import (
    DiscoverVideoCreate,
    DiscoverVideoUpdate,
)

from app.services.moderation_service import ModerationService

class DiscoverVideoService:
    """Business rules for SMS Discover."""

    def __init__(self, session: AsyncSession) -> None:
        self.athletes = AthleteRepository(session)
        self.videos = DiscoverVideoRepository(session)

        self.moderation = ModerationService(session)

    async def _get_athlete(self, athlete_id: uuid.UUID):
        athlete = await self.athletes.get_by_id(athlete_id)

        if athlete is None:
            raise NotFoundError("Athlete not found")

        return athlete

    async def _get_owned_athlete(
        self,
        athlete_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ):
        athlete = await self._get_athlete(athlete_id)

        if athlete.user_id != current_user_id:
            raise ForbiddenError(
                "You do not have permission to manage "
                "Discover videos for this athlete"
            )

        return athlete

    async def _get_video(
        self,
        video_id: uuid.UUID,
    ) -> DiscoverVideo:
        video = await self.videos.get_by_id(video_id)

        if video is None:
            raise NotFoundError("Discover video not found")

        return video

    async def _get_owned_video(
        self,
        athlete_id: uuid.UUID,
        video_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> DiscoverVideo:
        await self._get_owned_athlete(
            athlete_id,
            current_user_id,
        )

        video = await self._get_video(video_id)

        if video.athlete_id != athlete_id:
            raise NotFoundError("Discover video not found")

        return video

    async def create_video(
        self,
        athlete_id: uuid.UUID,
        data: DiscoverVideoCreate,
        current_user_id: uuid.UUID,
    ) -> DiscoverVideo:
        await self._get_owned_athlete(
            athlete_id,
            current_user_id,
        )

        video = DiscoverVideo(
            athlete_id=athlete_id,
            video_url=str(data.video_url),
            thumbnail_url=(
                str(data.thumbnail_url)
                if data.thumbnail_url is not None
                else None
            ),
            caption=data.caption,
            duration_seconds=data.duration_seconds,
            visibility=data.visibility,
            publication_status="draft",
            moderation_status="pending",
            is_active=True,
            view_count=0,
        )

        return await self.videos.create(video)

    async def get_video(
        self,
        athlete_id: uuid.UUID,
        video_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> DiscoverVideo:
        return await self._get_owned_video(
            athlete_id,
            video_id,
            current_user_id,
        )

    async def list_athlete_videos(
        self,
        athlete_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> Sequence[DiscoverVideo]:
        await self._get_owned_athlete(
            athlete_id,
            current_user_id,
        )

        return await self.videos.list_by_athlete_id(
            athlete_id
        )

    async def list_public_discover(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[DiscoverVideo]:
        return await self.videos.list_public_discover(
            limit=limit,
            offset=offset,
        )

    async def update_video(
        self,
        athlete_id: uuid.UUID,
        video_id: uuid.UUID,
        data: DiscoverVideoUpdate,
        current_user_id: uuid.UUID,
    ) -> DiscoverVideo:
        video = await self._get_owned_video(
            athlete_id,
            video_id,
            current_user_id,
        )

        updates = data.model_dump(exclude_unset=True)

        if "video_url" in updates:
            value = updates["video_url"]
            updates["video_url"] = (
                str(value) if value is not None else None
            )

        if "thumbnail_url" in updates:
            value = updates["thumbnail_url"]
            updates["thumbnail_url"] = (
                str(value) if value is not None else None
            )

        substantive_fields = {
            "video_url",
            "thumbnail_url",
            "caption",
            "duration_seconds",
            "visibility",
        }

        content_changed = any(
            field in substantive_fields
            and getattr(video, field) != value
            for field, value in updates.items()
        )

        for field, value in updates.items():
            setattr(video, field, value)

        if (
            content_changed
            and video.moderation_status != "pending"
        ):
            video.moderation_status = "pending"

        video = await self.videos.update(video)

        if (
            content_changed
            and video.publication_status == "published"
        ):
            await self.moderation.create_publication_review(
                owner_user_id=current_user_id,
                video_id=video.id,
            )

        return video

    async def request_publication(
        self,
        athlete_id: uuid.UUID,
        video_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> DiscoverVideo:
        """Submit an owned Discover video for publication review."""

        video = await self._get_owned_video(
            athlete_id,
            video_id,
            current_user_id,
        )

        if not video.is_active:
            raise ForbiddenError(
                "Inactive Discover video cannot be published"
            )

        video.publication_status = "published"
        video.moderation_status = "pending"

        video = await self.videos.update(video)

        await self.moderation.create_publication_review(
            owner_user_id=current_user_id,
            video_id=video.id,
        )

        return video

    async def delete_video(
        self,
        athlete_id: uuid.UUID,
        video_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> None:
        video = await self._get_owned_video(
            athlete_id,
            video_id,
            current_user_id,
        )

        await self.videos.delete(video)
