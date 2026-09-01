"""Repository for SMS Discover videos."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discover_video import DiscoverVideo


class DiscoverVideoRepository:
    """Database operations for SMS Discover videos."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        video: DiscoverVideo,
    ) -> DiscoverVideo:
        self.session.add(video)
        await self.session.flush()
        await self.session.refresh(video)
        return video

    async def get_by_id(
        self,
        video_id: uuid.UUID,
    ) -> DiscoverVideo | None:
        result = await self.session.execute(
            select(DiscoverVideo).where(
                DiscoverVideo.id == video_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_athlete_id(
        self,
        athlete_id: uuid.UUID,
    ) -> Sequence[DiscoverVideo]:
        result = await self.session.execute(
            select(DiscoverVideo)
            .where(
                DiscoverVideo.athlete_id == athlete_id
            )
            .order_by(DiscoverVideo.created_at.desc())
        )
        return result.scalars().all()

    async def list_public_discover(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[DiscoverVideo]:
        result = await self.session.execute(
            select(DiscoverVideo)
            .where(
                DiscoverVideo.publication_status == "published",
                DiscoverVideo.moderation_status == "approved",
                DiscoverVideo.visibility == "public",
                DiscoverVideo.is_active.is_(True),
            )
            .order_by(DiscoverVideo.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def update(
        self,
        video: DiscoverVideo,
    ) -> DiscoverVideo:
        await self.session.flush()
        await self.session.refresh(video)
        return video

    async def delete(
        self,
        video: DiscoverVideo,
    ) -> None:
        await self.session.delete(video)
        await self.session.flush()
