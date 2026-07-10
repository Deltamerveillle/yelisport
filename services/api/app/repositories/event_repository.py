"""Persistence operations for events and registrations."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, EventRegistration, RegistrationStatus


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, event: Event) -> Event:
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def list_upcoming(self) -> list[Event]:
        result = await self.session.scalars(
            select(Event).where(Event.ends_at > datetime.now(UTC)).order_by(Event.starts_at)
        )
        return list(result.all())

    async def get(self, event_id: uuid.UUID) -> Event | None:
        return await self.session.get(Event, event_id)

    async def get_for_registration(self, event_id: uuid.UUID) -> Event | None:
        return await self.session.scalar(
            select(Event).where(Event.id == event_id).with_for_update()
        )

    async def registered_count(self, event_id: uuid.UUID) -> int:
        count = await self.session.scalar(
            select(func.count(EventRegistration.id)).where(
                EventRegistration.event_id == event_id,
                EventRegistration.status == RegistrationStatus.REGISTERED,
            )
        )
        return int(count or 0)

    async def get_registration(
        self, event_id: uuid.UUID, user_id: uuid.UUID
    ) -> EventRegistration | None:
        return await self.session.scalar(
            select(EventRegistration).where(
                EventRegistration.event_id == event_id,
                EventRegistration.user_id == user_id,
            )
        )

    async def save_registration(self, registration: EventRegistration) -> EventRegistration:
        self.session.add(registration)
        await self.session.commit()
        await self.session.refresh(registration)
        return registration

    async def list_for_user(self, user_id: uuid.UUID) -> list[Event]:
        result = await self.session.scalars(
            select(Event)
            .join(EventRegistration, EventRegistration.event_id == Event.id)
            .where(
                EventRegistration.user_id == user_id,
                EventRegistration.status == RegistrationStatus.REGISTERED,
            )
            .order_by(Event.starts_at)
        )
        return list(result.all())
