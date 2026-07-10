"""Version 1 API routes."""

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.events import router as events_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.sports import router as sports_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(sports_router)
router.include_router(events_router)
