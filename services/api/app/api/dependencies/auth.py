"""FastAPI dependencies for authenticated routes."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.schemas.auth import AuthUser
from app.services.auth_service import AuthService

bearer = HTTPBearer(auto_error=True)


def get_auth_service() -> AuthService:
    return AuthService()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthUser:
    return service.user_from_token(credentials.credentials)


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
