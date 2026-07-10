"""Schemas shared by API endpoints."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str
    environment: str
    timestamp: datetime

    @classmethod
    def healthy(cls, *, service: str, version: str, environment: str) -> "HealthResponse":
        return cls(
            service=service,
            version=version,
            environment=environment,
            timestamp=datetime.now(UTC),
        )


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str
