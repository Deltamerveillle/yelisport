"""Owned athlete media registry. Upload bytes only through private Supabase Storage."""

import uuid
from typing import Annotated

import httpx

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.core.config import get_settings
from app.core.exceptions import ApplicationError, ForbiddenError, NotFoundError
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


class UploadIntentRequest(BaseModel):
    """Only the server creates the object path, never the caller."""
    media_type: str
    mime_type: str


@router.post("/upload-intent")
async def create_upload_intent(
    athlete_id: uuid.UUID,
    payload: UploadIntentRequest,
    current_user: CurrentUser,
    session: Session,
) -> dict[str, str]:
    """Authorize a one-time private upload after checking ownership and plan."""
    user_id = uuid.UUID(str(current_user.id))
    await _owned_athlete(session, athlete_id, user_id)
    access = await SubscriptionService(session).get_access(user_id)
    if not access.has_premium_access:
        raise ForbiddenError("Abonnement actif requis avant téléversement")
    if payload.mime_type not in _EXTENSIONS:
        raise ForbiddenError("Format de média non autorisé")
    if (
        payload.media_type == "photo"
        and not payload.mime_type.startswith("image/")
    ) or (
        payload.media_type == "video"
        and payload.mime_type != "video/mp4"
    ):
        raise ForbiddenError("Type de média incompatible")

    settings = get_settings()
    if (
        not settings.supabase_url.startswith("https://")
        or settings.supabase_service_role_key in ("", "change-me")
    ):
        raise ApplicationError(
            "Téléversement temporairement indisponible",
            status_code=503,
        )

    path = f"{user_id}/{athlete_id}/{uuid.uuid4()}.{_EXTENSIONS[payload.mime_type]}"
    url = (
        settings.supabase_url.rstrip("/")
        + "/storage/v1/object/upload/sign/sms24-athlete-media/"
        + path
    )
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(url, headers=headers, json={})
        response.raise_for_status()
        signed = response.json()
        token = signed.get("token")
        if not isinstance(token, str) or not token:
            raise ValueError("Missing signed upload token")
    except (httpx.HTTPError, ValueError) as exc:
        raise ApplicationError(
            "Autorisation de téléversement indisponible", status_code=503,
        ) from exc
    return {"path": path, "token": token}


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
