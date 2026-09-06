"""SMS24 sports-data provider contracts."""

from app.sms24.providers.base import (
    ProviderCompetition,
    ProviderFetchResult,
    ProviderFixture,
    ProviderHealthResult,
    ProviderParticipant,
    SportsDataProvider,
)
from app.sms24.providers.registry import ProviderRegistry

__all__ = [
    "ProviderCompetition",
    "ProviderFetchResult",
    "ProviderFixture",
    "ProviderHealthResult",
    "ProviderParticipant",
    "ProviderRegistry",
    "SportsDataProvider",
]
