"""Authentication request and response contracts."""

from pydantic import BaseModel, EmailStr, Field


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, min_length=2, max_length=80)


class SignInRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class AuthUser(BaseModel):
    id: str
    email: EmailStr | None = None


class AuthSession(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"
    user: AuthUser


class SignUpResponse(BaseModel):
    user: AuthUser
    session: AuthSession | None = None
    confirmation_required: bool


class MessageResponse(BaseModel):
    message: str
