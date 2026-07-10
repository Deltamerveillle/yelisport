"""Exception handlers with a stable public error shape."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import ApplicationError


async def application_error_handler(request: Request, exc: ApplicationError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )
