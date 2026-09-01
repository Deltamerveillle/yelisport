"""Version 1 API routes."""

from fastapi import APIRouter

from app.api.v1.endpoints import athlete_passports
from app.api.v1.endpoints import discover_videos
from app.api.v1.endpoints import subscriptions
from app.api.v1.endpoints.athletes import router as athletes_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.events import router as events_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.sports import router as sports_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(sports_router)
router.include_router(events_router)
router.include_router(athletes_router)
router.include_router(athlete_passports.router)
router.include_router(discover_videos.router)

router.include_router(
    subscriptions.router,
    prefix="/subscriptions",
    tags=["subscriptions"],
)
