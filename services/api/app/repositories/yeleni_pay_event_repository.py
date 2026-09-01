"""Repository for received YELENI Pay events."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.yeleni_pay_event import YeleniPayEvent


class YeleniPayEventRepository:
    """Database operations for YELENI Pay event idempotency."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        event: YeleniPayEvent,
    ) -> YeleniPayEvent:
        self.session.add(event)

        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raise

        await self.session.refresh(event)
        return event

    async def get_by_event_id(
        self,
        event_id: str,
    ) -> YeleniPayEvent | None:
        result = await self.session.execute(
            select(YeleniPayEvent).where(
                YeleniPayEvent.event_id == event_id
            )
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        event: YeleniPayEvent,
    ) -> YeleniPayEvent:
        await self.session.flush()
        await self.session.refresh(event)
        return event
