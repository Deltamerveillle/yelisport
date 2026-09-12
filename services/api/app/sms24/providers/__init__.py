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

from app.sms24.providers.standings import (
    ProviderStanding,
    ProviderStandingsRequest,
    ProviderStandingsResult,
)

__all__ = [
    "ProviderStanding",
    "ProviderStandingsRequest",
    "ProviderStandingsResult",
    "ProviderCompetition",
    "ProviderFetchResult",
    "ProviderFixture",
    "ProviderHealthResult",
    "ProviderParticipant",
    "ProviderRegistry",
    "SportsDataProvider",
]
