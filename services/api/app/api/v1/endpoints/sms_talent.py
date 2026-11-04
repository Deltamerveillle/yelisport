"""Authenticated SMS Talent qualification endpoint."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db_session
from app.repositories.talent_application_repository import TalentApplicationRepository
from app.services.talent_service import TalentService

router = APIRouter(prefix="/talent", tags=["SMS Talent"])


@router.get("/applications/{application_id}/qualification")
async def get_talent_qualification(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    application = await TalentApplicationRepository(session).get_by_id(
        application_id
    )

    if application is None:
        raise NotFoundError("Candidature introuvable")

    if application.user_id != uuid.UUID(str(current_user.id)):
        raise ForbiddenError("Accès interdit à cette candidature")

    if application.status != "completed":
        raise ConflictError("Les trois évaluations ne sont pas terminées")

    service = TalentService(session)

    qualification = await service.get_qualification_status(
        application_id=application_id
    )
    return {"qualification_status": qualification}
