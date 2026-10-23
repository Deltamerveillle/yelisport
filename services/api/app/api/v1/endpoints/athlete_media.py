"""Owned athlete media registry. Upload bytes only through private Supabase Storage."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db_session
from app.models.athlete_media import AthleteMedia
from app.repositories.athlete_repository import AthleteRepository
from app.schemas.athlete_media import AthleteMediaCreate, AthleteMediaResponse
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/athletes/{athlete_id}/media", tags=["SMS athlete media"])
Session = Annotated[AsyncSession, Depends(get_db_session)]

_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "video/mp4": "mp4",
}


async def _owned_athlete(
    session: AsyncSession, athlete_id: uuid.UUID, user_id: uuid.UUID,
) -> None:
    athlete = await AthleteRepository(session).get_by_id(athlete_id)
    if athlete is None or athlete.user_id != user_id:
        raise NotFoundError("Profil sportif introuvable")


@router.get("", response_model=list[AthleteMediaResponse])
async def list_my_media(
    athlete_id: uuid.UUID, current_user: CurrentUser, session: Session,
) -> list[AthleteMedia]:
    user_id = uuid.UUID(str(current_user.id))
    await _owned_athlete(session, athlete_id, user_id)
    return list(await session.scalars(
        select(AthleteMedia).where(AthleteMedia.athlete_id == athlete_id)
        .order_by(AthleteMedia.created_at.desc()),
    ))


@router.post(
    "", response_model=AthleteMediaResponse, status_code=status.HTTP_201_CREATED,
)
async def register_uploaded_media(
    athlete_id: uuid.UUID, data: AthleteMediaCreate,
    current_user: CurrentUser, session: Session,
) -> AthleteMedia:
    user_id = uuid.UUID(str(current_user.id))
    await _owned_athlete(session, athlete_id, user_id)

    access = await SubscriptionService(session).get_access(user_id)
    if not access.has_premium_access:
        raise ForbiddenError("Abonnement actif requis pour déposer des médias")

    expected = _EXTENSIONS[data.mime_type]
    if data.media_type == "photo" and not data.mime_type.startswith("image/"):
        raise ForbiddenError("La photo doit être une image")
    if data.media_type == "video" and data.mime_type != "video/mp4":
        raise ForbiddenError("La vidéo doit être au format MP4")
    if data.media_type == "video" and data.duration_seconds is None:
        raise ForbiddenError("Durée vidéo requise (15 à 30 secondes)")
    if data.media_type == "photo" and data.duration_seconds is not None:
        raise ForbiddenError("Une photo ne possède pas de durée")

    path = data.storage_path
    parts = path.split("/")
    # User-controlled arbitrary URLs or references to another user's bucket are forbidden.
    if (
        len(parts) != 3
        or parts[0] != str(user_id)
        or parts[1] != str(athlete_id)
        or not parts[2].endswith("." + expected)
    ):
        raise ForbiddenError("Chemin de média non autorisé")
    try:
        uuid.UUID(parts[2].split(".")[0])
    except (TypeError, ValueError) as exc:
        raise ForbiddenError("Nom de média non autorisé") from exc

    item = AthleteMedia(
        athlete_id=athlete_id,
        storage_path=path,
        media_type=data.media_type,
        mime_type=data.mime_type,
        duration_seconds=data.duration_seconds,
        moderation_status="pending",
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item
