"""Event creation and registration use cases."""

import uuid
from datetime import UTC, datetime

from app.core.exceptions import ConflictError, NotFoundError
from app.models.event import Event, EventRegistration, RegistrationStatus
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventCreate


class EventService:
    def __init__(self, repository: EventRepository) -> None:
        self.repository = repository

    async def create(self, payload: EventCreate, organizer_id: uuid.UUID) -> Event:
        return await self.repository.create(
            Event(**payload.model_dump(), organizer_id=organizer_id)
        )

    async def list_upcoming(self) -> list[Event]:
        return await self.repository.list_upcoming()

    async def register(self, event_id: uuid.UUID, user_id: uuid.UUID) -> EventRegistration:
        event = await self.repository.get_for_registration(event_id)
        if event is None:
            raise NotFoundError("Événement introuvable")
        registration = await self.repository.get_registration(event_id, user_id)
        if registration and registration.status == RegistrationStatus.REGISTERED:
            return registration
        if await self.repository.registered_count(event_id) >= event.capacity:
            raise ConflictError("Événement complet")
        if registration:
            registration.status = RegistrationStatus.REGISTERED
            registration.cancelled_at = None
            registration.registered_at = datetime.now(UTC)
        else:
            registration = EventRegistration(event_id=event_id, user_id=user_id)
        return await self.repository.save_registration(registration)

    async def list_mine(self, user_id: uuid.UUID) -> list[Event]:
        return await self.repository.list_for_user(user_id)

    async def cancel(self, event_id: uuid.UUID, user_id: uuid.UUID) -> EventRegistration:
        registration = await self.repository.get_registration(event_id, user_id)
        if registration is None or registration.status != RegistrationStatus.REGISTERED:
            raise NotFoundError("Inscription active introuvable")
        registration.status = RegistrationStatus.CANCELLED
        registration.cancelled_at = datetime.now(UTC)
        return await self.repository.save_registration(registration)
