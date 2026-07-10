"""Authenticated event and registration endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db_session
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventCreate, EventResponse, RegistrationResponse
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["events"])
Session = Annotated[AsyncSession, Depends(get_db_session)]


def get_event_service(session: Session) -> EventService:
    return EventService(EventRepository(session))


EventServiceDependency = Annotated[EventService, Depends(get_event_service)]


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    current_user: CurrentUser,
    event_service: EventServiceDependency,
) -> EventResponse:
    event = await event_service.create(payload, uuid.UUID(current_user.id))
    return EventResponse.model_validate(event)


@router.get("", response_model=list[EventResponse])
async def list_events(
    current_user: CurrentUser, event_service: EventServiceDependency
) -> list[EventResponse]:
    del current_user
    events = await event_service.list_upcoming()
    return [EventResponse.model_validate(event) for event in events]


@router.get("/mine", response_model=list[EventResponse])
async def list_my_events(
    current_user: CurrentUser, event_service: EventServiceDependency
) -> list[EventResponse]:
    events = await event_service.list_mine(uuid.UUID(current_user.id))
    return [EventResponse.model_validate(event) for event in events]


@router.post("/{event_id}/registrations", response_model=RegistrationResponse)
async def register_for_event(
    event_id: uuid.UUID,
    current_user: CurrentUser,
    event_service: EventServiceDependency,
) -> RegistrationResponse:
    registration = await event_service.register(event_id, uuid.UUID(current_user.id))
    return RegistrationResponse(event_id=registration.event_id, status=registration.status.value)


@router.delete("/{event_id}/registrations/me", response_model=RegistrationResponse)
async def cancel_registration(
    event_id: uuid.UUID,
    current_user: CurrentUser,
    event_service: EventServiceDependency,
) -> RegistrationResponse:
    registration = await event_service.cancel(event_id, uuid.UUID(current_user.id))
    return RegistrationResponse(event_id=registration.event_id, status=registration.status.value)
