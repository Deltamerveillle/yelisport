"""Internal YeliSport AI service."""

import logging

from fastapi import FastAPI

from app.api.router import router
from app.config.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper(), force=True)
    application = FastAPI(
        title="YeliSport AI",
        version="0.1.0",
        docs_url=None if settings.app_env == "production" else "/docs",
    )
    application.include_router(router, prefix=settings.api_prefix)
    return application


app = create_app()
