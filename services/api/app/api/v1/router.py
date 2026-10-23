"""Version 1 API routes."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    athlete_country_eligibilities,
    athlete_passports,
    athlete_media,
    athlete_performances,
    countries,
    discover_athletes,
    discover_videos,
    moderation,
    notifications,
    payments,
    sms24_live,
    sms24_news,
    sms_connect,
    sms_nations,
    sms_proof,
    subscriptions,
)
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
router.include_router(athlete_media.router)
router.include_router(athlete_performances.router)
router.include_router(athlete_country_eligibilities.router)
router.include_router(countries.router)
router.include_router(discover_athletes.router)
router.include_router(discover_videos.router)
router.include_router(sms_nations.router)
router.include_router(sms_proof.router)
router.include_router(sms_connect.router)
router.include_router(sms24_live.router)
router.include_router(sms24_news.router)
router.include_router(notifications.router)
router.include_router(payments.router)

router.include_router(
    subscriptions.router,
    prefix="/subscriptions",
    tags=["subscriptions"],
)
router.include_router(moderation.router)
