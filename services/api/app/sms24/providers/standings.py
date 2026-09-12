"""Provider-independent standings observations; missing statistics remain unknown."""

from dataclasses import dataclass
from datetime import datetime

from app.sms24.providers.base import ProviderParticipant


@dataclass(slots=True)
class ProviderStanding:
    participant: ProviderParticipant
    position: int
    points: int | None = None
    played: int | None = None
    wins: int | None = None
    draws: int | None = None
    losses: int | None = None
    goals_for: int | None = None
    goals_against: int | None = None
    goal_difference: int | None = None
    home_played: int | None = None
    home_wins: int | None = None
    home_draws: int | None = None
    home_losses: int | None = None
    home_goals_for: int | None = None
    home_goals_against: int | None = None
    home_points: int | None = None
    away_played: int | None = None
    away_wins: int | None = None
    away_draws: int | None = None
    away_losses: int | None = None
    away_goals_for: int | None = None
    away_goals_against: int | None = None
    away_points: int | None = None
    external_id: str | None = None
    external_competition_id: str | None = None
    external_season_id: str | None = None
    form: str | None = None
    description: str | None = None
    movement_status: str | None = None
    stage_external_id: str | None = None
    group_external_id: str | None = None
    group_name: str | None = None
    round_external_id: str | None = None
    standing_rule_external_id: str | None = None
    provider_updated_at: datetime | None = None


@dataclass(slots=True)
class ProviderStandingsResult:
    rows: list[ProviderStanding]
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderStandingsRequest:
    """Explicit provider mapping: API-Football year or Sportmonks season ID.

    This is not a canonical SportsSeason label. The caller supplies the mapping.
    API-Football additionally requires league_external_id.
    """

    season: str
    league_external_id: str | None = None


def validate_standings_request(request: ProviderStandingsRequest) -> None:
    for name, value in (
        ("season", request.season),
        ("league_external_id", request.league_external_id),
    ):
        if value is None and name == "league_external_id":
            continue
        if not isinstance(value, str) or not value.strip() or len(value) > 160:
            raise ValueError(f"Standings {name} must be a nonempty provider identifier")
