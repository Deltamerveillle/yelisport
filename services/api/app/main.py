"""YeliSport public API application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.error_handler import application_error_handler
from app.api.middleware.request_context import RequestContextMiddleware
from app.api.router import router
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)
    application = FastAPI(
        title="YeliSport API",
        version="0.1.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
    )
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_exception_handler(ApplicationError, application_error_handler)  # type: ignore[arg-type]
    application.include_router(router, prefix=settings.api_prefix)
    return application


app = create_app()
