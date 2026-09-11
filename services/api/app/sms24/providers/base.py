"""Provider contracts for SMS24 sports data ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ProviderParticipant:
    external_id: str
    name: str
    competitor_type: str = "team"
    short_name: str | None = None
    country_code: str | None = None
    logo_url: str | None = None
    position: int = 0
    role: str | None = None
    score: dict[str, Any] = field(default_factory=dict)
    result_status: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderCompetition:
    external_id: str
    name: str
    country_code: str | None = None
    season: str | None = None
    logo_url: str | None = None
    source_updated_at: datetime | None = None

    jurisdiction_name: str | None = None


@dataclass(slots=True)
class ProviderFixture:
    external_id: str
    sport_slug: str
    starts_at: datetime
    status: str

    name: str | None = None
    live_clock: str | None = None
    venue: str | None = None

    competition: ProviderCompetition | None = None
    participants: list[ProviderParticipant] = field(default_factory=list)

    result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    source_updated_at: datetime | None = None


@dataclass(slots=True)
class ProviderFetchResult:
    fixtures: list[ProviderFixture] = field(default_factory=list)
    fetched_at: datetime | None = None
    raw_count: int = 0


@dataclass(slots=True)
class ProviderHealthResult:
    is_healthy: bool
    checked_at: datetime
    latency_ms: int | None = None
    message: str | None = None


class SportsDataProvider(ABC):
    """Abstract contract implemented by every SMS24 sports provider."""

    slug: str
    name: str

    @abstractmethod
    async def fetch_fixtures(
        self,
        *,
        sport_slug: str | None = None,
        starts_from: datetime | None = None,
        starts_until: datetime | None = None,
        live_only: bool = False,
    ) -> ProviderFetchResult:
        """Fetch provider fixtures in normalized provider-independent form."""

    @abstractmethod
    async def check_health(self) -> ProviderHealthResult:
        """Check whether the provider is reachable and usable."""
