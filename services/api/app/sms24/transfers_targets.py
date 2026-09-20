"""Bounded read-only discovery from provider team observations; no identity resolution."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sport import Sport
from app.models.sports_live import SportsCompetitor
from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.registry import ProviderRegistry
from app.sms24.providers.sportmonks import SportmonksProvider
from app.sms24.runner import SMS24RunnerRepository


def validate_target_cursor(cursor: str | None) -> None:
    if cursor is not None:
        if not isinstance(cursor, str):
            raise ValueError("Target cursor must be a provider identifier")
        SportmonksProvider._transfer_id(cursor)


@dataclass(frozen=True, slots=True)
class TransfersDiscoveryAttempt:
    team_external_id: str
    success: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class TransfersTargetDiscoveryResult:
    player_ids: tuple[str, ...] = ()
    attempts: tuple[TransfersDiscoveryAttempt, ...] = ()
    teams_limited: bool = False
    reason: str | None = None
    next_cursor: str | None = None

    @property
    def has_more(self) -> bool:
        return self.teams_limited


class SportmonksTransfersTargetDiscovery:
    def __init__(
        self,
        *,
        session: AsyncSession,
        registry: ProviderRegistry,
        max_teams: int = 20,
    ) -> None:
        if type(max_teams) is not int or max_teams < 1:
            raise ValueError("max_teams must be a positive integer")
        self.session = session
        self.registry = registry
        self.max_teams = max_teams
        self.repository = SMS24RunnerRepository(session)

    async def discover(
        self,
        *,
        reference_date: date,
        after_team_external_id: str | None = None,
    ) -> TransfersTargetDiscoveryResult:
        validate_target_cursor(after_team_external_id)
        if type(reference_date) is not date:
            raise ValueError("Supply an explicit discovery reference date")
        source = await self.repository.get_active_source_for_capability("sportmonks", "transfers")
        if source is None:
            return TransfersTargetDiscoveryResult(reason="transfers_capability_not_active")
        try:
            provider = self.registry.get("sportmonks")
        except KeyError:
            return TransfersTargetDiscoveryResult(reason="provider_not_registered")
        fetch = getattr(provider, "fetch_team_player_ids", None)
        if not callable(fetch):
            return TransfersTargetDiscoveryResult(reason="target_discovery_not_supported")
        teams = list(
            await self.session.scalars(
                select(SportsCompetitor.external_id)
                .join(Sport, Sport.id == SportsCompetitor.sport_id)
                .where(
                    SportsCompetitor.source_id == source.id,
                    SportsCompetitor.competitor_type == "team",
                    Sport.slug == "football",
                    Sport.is_active.is_(True),
                    SportsCompetitor.external_id.collate("C") > after_team_external_id
                    if after_team_external_id is not None
                    else True,
                )
                .order_by(SportsCompetitor.external_id.collate("C"))
                .limit(self.max_teams + 1)
            )
        )
        players = set()
        attempts = []
        for team_id in teams[: self.max_teams]:
            try:
                discovered = await fetch(team_external_id=team_id, reference_date=reference_date)
            except SQLAlchemyError:
                raise
            except ProviderAccessRestrictedError:
                attempts.append(
                    TransfersDiscoveryAttempt(team_id, False, "provider_access_restricted")
                )
                continue
            except Exception:
                attempts.append(
                    TransfersDiscoveryAttempt(team_id, False, "discovery_payload_failed")
                )
                continue
            players.update(discovered)
            attempts.append(TransfersDiscoveryAttempt(team_id, True))
        return TransfersTargetDiscoveryResult(
            player_ids=tuple(sorted(players)),
            attempts=tuple(attempts),
            teams_limited=len(teams) > self.max_teams,
            next_cursor=teams[self.max_teams - 1] if len(teams) > self.max_teams else None,
        )
