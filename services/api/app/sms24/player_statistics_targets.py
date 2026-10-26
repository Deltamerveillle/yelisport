"""Discover bounded Player Statistics targets from provider-owned athlete identities.

Targets come only from existing SMS24 provider competitors with a provider-scoped
canonical identity. This layer never resolves, creates, or infers a human identity.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sport import Sport
from app.models.sports_live import SportsCanonicalCompetitor, SportsCompetitor
from app.sms24.player_statistics_runner import PlayerStatisticsTarget
from app.sms24.runner import SMS24RunnerRepository


def validate_statistics_target_cursor(value: str | None) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("Invalid Player Statistics target cursor")
    if len(value) > 160 or "\x00" in value:
        raise ValueError("Invalid Player Statistics target cursor")


@dataclass(frozen=True, slots=True)
class AutomaticPlayerStatisticsTarget:
    provider_slug: str
    athlete_external_id: str
    sport_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PlayerStatisticsTargetDiscoveryResult:
    targets: tuple[AutomaticPlayerStatisticsTarget, ...] = ()
    reason: str | None = None
    next_cursor: str | None = None

    @property
    def has_more(self) -> bool:
        return self.next_cursor is not None


class PlayerStatisticsTargetDiscovery:
    """Select existing provider athlete identities; never infer human identity."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        provider_slug: str = "sportmonks",
        max_players: int = 100,
    ) -> None:
        if not isinstance(provider_slug, str) or not provider_slug:
            raise ValueError("provider_slug is required")
        if provider_slug != provider_slug.strip().lower():
            raise ValueError("provider_slug must be normalized")
        if type(max_players) is not int or max_players < 1:
            raise ValueError("max_players must be a positive integer")

        self.session = session
        self.provider_slug = provider_slug
        self.max_players = max_players
        self.repository = SMS24RunnerRepository(session)

    async def discover(
        self,
        *,
        after_player_external_id: str | None = None,
    ) -> PlayerStatisticsTargetDiscoveryResult:
        validate_statistics_target_cursor(after_player_external_id)

        source = await self.repository.get_active_source_for_capability(
            self.provider_slug,
            "statistics",
        )
        if source is None:
            return PlayerStatisticsTargetDiscoveryResult(
                reason="statistics_capability_not_active"
            )

        rows = list(
            (
                await self.session.execute(
                    select(
                        SportsCompetitor.external_id,
                        SportsCompetitor.sport_id,
                    )
                    .join(Sport, Sport.id == SportsCompetitor.sport_id)
                    .join(
                        SportsCanonicalCompetitor,
                        SportsCanonicalCompetitor.id
                        == SportsCompetitor.canonical_competitor_id,
                    )
                    .where(
                        SportsCompetitor.source_id == source.id,
                        SportsCompetitor.competitor_type == "athlete",
                        SportsCanonicalCompetitor.competitor_type == "athlete",
                        SportsCanonicalCompetitor.identity_scope == "provider_scoped",
                        SportsCanonicalCompetitor.sport_id == SportsCompetitor.sport_id,
                        Sport.is_active.is_(True),
                        SportsCompetitor.external_id.collate("C")
                        > after_player_external_id
                        if after_player_external_id is not None
                        else true(),
                    )
                    .order_by(SportsCompetitor.external_id.collate("C"))
                    .limit(self.max_players + 1)
                )
            ).all()
        )

        selected = rows[: self.max_players]
        targets = tuple(
            AutomaticPlayerStatisticsTarget(
                provider_slug=self.provider_slug,
                athlete_external_id=external_id,
                sport_id=sport_id,
            )
            for external_id, sport_id in selected
        )

        return PlayerStatisticsTargetDiscoveryResult(
            targets=targets,
            next_cursor=(
                selected[-1][0] if len(rows) > self.max_players and selected else None
            ),
        )


def as_runner_target(
    target: AutomaticPlayerStatisticsTarget,
) -> dict[str, PlayerStatisticsTarget]:
    if type(target) is not AutomaticPlayerStatisticsTarget:
        raise ValueError("AutomaticPlayerStatisticsTarget required")
    return {
        target.provider_slug: PlayerStatisticsTarget(
            target.athlete_external_id,
            target.sport_id,
        )
    }
