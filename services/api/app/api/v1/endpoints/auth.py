"""Supabase-backed authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from app.api.dependencies.auth import CurrentUser, get_auth_service
from app.schemas.auth import (
    AuthSession,
    AuthUser,
    MessageResponse,
    RefreshRequest,
    SignInRequest,
    SignUpRequest,
    SignUpResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/sign-up", response_model=SignUpResponse, status_code=status.HTTP_201_CREATED)
def sign_up(payload: SignUpRequest, service: AuthServiceDependency) -> SignUpResponse:
    return service.sign_up(str(payload.email), payload.password, payload.display_name)


@router.post("/sign-in", response_model=AuthSession)
def sign_in(payload: SignInRequest, service: AuthServiceDependency) -> AuthSession:
    return service.sign_in(str(payload.email), payload.password)


@router.post("/refresh", response_model=AuthSession)
def refresh(payload: RefreshRequest, service: AuthServiceDependency) -> AuthSession:
    return service.refresh(payload.refresh_token)


@router.get("/me", response_model=AuthUser)
def me(current_user: CurrentUser) -> AuthUser:
    return current_user


@router.post("/sign-out", response_model=MessageResponse)
def sign_out(
    service: AuthServiceDependency,
    authorization: Annotated[str, Header(pattern=r"^Bearer .+")],
) -> MessageResponse:
    service.sign_out(authorization.removeprefix("Bearer "))
    return MessageResponse(message="Déconnexion réussie")
