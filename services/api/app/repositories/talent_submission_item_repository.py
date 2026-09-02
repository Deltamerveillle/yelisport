"""Repository for private SMS Talent submission items."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.talent_submission_item import TalentSubmissionItem


class TalentSubmissionItemRepository:
    """Database operations for SMS Talent submission materials."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        item: TalentSubmissionItem,
    ) -> TalentSubmissionItem:
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def get_by_id(
        self,
        item_id: uuid.UUID,
    ) -> TalentSubmissionItem | None:
        result = await self.session.execute(
            select(TalentSubmissionItem).where(
                TalentSubmissionItem.id == item_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_application_id(
        self,
        application_id: uuid.UUID,
    ) -> Sequence[TalentSubmissionItem]:
        result = await self.session.execute(
            select(TalentSubmissionItem)
            .where(
                TalentSubmissionItem.application_id == application_id
            )
            .order_by(
                TalentSubmissionItem.created_at.asc()
            )
        )
        return result.scalars().all()

    async def update(
        self,
        item: TalentSubmissionItem,
    ) -> TalentSubmissionItem:
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def delete(
        self,
        item: TalentSubmissionItem,
    ) -> None:
        await self.session.delete(item)
        await self.session.flush()
