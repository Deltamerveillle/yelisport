"""Private AI service routes."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config.settings import Settings, get_settings


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "ai"
    version: str = "0.1.0"
    environment: str
    timestamp: datetime


router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(environment=settings.app_env, timestamp=datetime.now(UTC))
