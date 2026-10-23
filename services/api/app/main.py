"""YeliSport public API application factory."""

import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.error_handler import application_error_handler
from app.api.middleware.request_context import RequestContextMiddleware
from app.api.router import router
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.core.logging import configure_logging


@asynccontextmanager
async def sms24_lifespan(_application: FastAPI):
    """Run optional SMS24 ingestion while this web instance is active.

    This is a best-effort fallback for a single-instance deployment, not a
    substitute for an always-on scheduled worker.
    """
    task = None
    enabled = os.getenv("SMS24_WORKER_ENABLED", "false").strip().lower()
    if enabled in {"1", "true", "yes", "on"}:
        from app.sms24.worker import run_worker

        task = asyncio.create_task(run_worker(), name="sms24-data-ingestion")
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)
    application = FastAPI(
        title="YeliSport API",
        lifespan=sms24_lifespan,
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
