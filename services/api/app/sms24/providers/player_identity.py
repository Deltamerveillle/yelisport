"""Provider-owned player identity; never an SMS human identity or verification."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


def validate_player_identity_text(value: str, limit: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise ValueError("Invalid provider player identity text")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderPlayerIdentity:
    external_id: str
    name: str
    fetched_at: datetime

    def __post_init__(self) -> None:
        validate_player_identity(self)


def validate_player_identity(value: ProviderPlayerIdentity) -> None:
    if not isinstance(value, ProviderPlayerIdentity):
        raise ValueError("Invalid provider player identity")
    validate_player_identity_text(value.external_id, 160)
    validate_player_identity_text(value.name, 200)
    if (
        not isinstance(value.fetched_at, datetime)
        or value.fetched_at.tzinfo is None
        or value.fetched_at.utcoffset() is None
    ):
        raise ValueError("Player identity timestamp must be timezone-aware")


class PlayerIdentityProvider(Protocol):
    async def fetch_team_player_ids(
        self,
        *,
        team_external_id: str,
        reference_date: date,
    ) -> tuple[str, ...]: ...

    async def fetch_player_identity(
        self,
        *,
        athlete_external_id: str,
    ) -> ProviderPlayerIdentity: ...
