"""FastAPI dependencies for authenticated routes."""

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApplicationError
from app.db.session import get_db_session
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthUser
from app.services.auth_service import AuthService


bearer = HTTPBearer(auto_error=True)


def get_auth_service() -> AuthService:
    return AuthService()


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials,
        Depends(bearer),
    ],
    service: Annotated[
        AuthService,
        Depends(get_auth_service),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
) -> AuthUser:
    auth_user = service.user_from_token(
        credentials.credentials
    )

    try:
        user_id = uuid.UUID(
            str(auth_user.id)
        )
    except (TypeError, ValueError) as exc:
        raise ApplicationError(
            "Identité utilisateur invalide",
            code="invalid_user_identity",
            status_code=401,
        ) from exc

    repository = UserRepository(session)
    local_user = await repository.get_by_id(user_id)

    if local_user is None:
        if not auth_user.email:
            raise ApplicationError(
                "Adresse e-mail utilisateur introuvable",
                code="missing_user_email",
                status_code=401,
            )
        local_user = await repository.create(
            user_id=user_id,
            email=auth_user.email,
        )
        await session.commit()

    if not local_user.is_active:
        raise ApplicationError(
            "Compte suspendu",
            code="account_suspended",
            status_code=403,
        )

    return auth_user


CurrentUser = Annotated[
    AuthUser,
    Depends(get_current_user),
]
