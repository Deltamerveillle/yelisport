"""Explicit team-to-player ingestion, with caller-owned transactions and no human links."""

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sport import Sport
from app.models.sports_live import SportsCanonicalCompetitor, SportsCompetitor, SportsDataSource
from app.sms24.canonical_entities import build_canonical_competitor_key
from app.sms24.ingestion import SMS24IngestionRepository
from app.sms24.providers.base import ProviderParticipant
from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.player_identity import (
    PlayerIdentityProvider,
    validate_player_identity,
    validate_player_identity_text,
)
from app.sms24.providers.registry import ProviderRegistry


@dataclass(frozen=True, slots=True)
class PlayerIdentityTeamTarget:
    provider_slug: str
    team_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PlayerIdentityFailure:
    provider_slug: str
    team_id: uuid.UUID
    player_external_id: str | None
    reason: str


@dataclass(slots=True)
class PlayerIdentityDiscoveryResult:
    teams_processed: int = 0
    players_discovered: int = 0
    players_processed: int = 0
    failures: list[PlayerIdentityFailure] = field(default_factory=list)


class PlayerIdentityDiscovery:
    def __init__(self, *, session: AsyncSession, registry: ProviderRegistry) -> None:
        self.session = session
        self.registry = registry
        self.repository = SMS24IngestionRepository(session)

    async def run(
        self,
        *,
        targets: tuple[PlayerIdentityTeamTarget, ...],
        reference_date: date,
    ) -> PlayerIdentityDiscoveryResult:
        """Validate all targets first. Local failures continue; database failures propagate."""
        if type(targets) is not tuple or not targets or type(reference_date) is not date:
            raise ValueError("Explicit team targets and reference date are required")
        validated = []
        for target in targets:
            if (
                type(target) is not PlayerIdentityTeamTarget
                or type(target.team_id) is not uuid.UUID
            ):
                raise ValueError("Invalid player identity team target")
            slug = target.provider_slug
            if not isinstance(slug, str) or not slug or slug != slug.strip().lower():
                raise ValueError("Invalid provider slug")
            team = await self.session.get(SportsCompetitor, target.team_id)
            if team is None or team.competitor_type != "team":
                raise ValueError("Unknown team target")
            source = await self.session.get(SportsDataSource, team.source_id)
            sport = await self.session.get(Sport, team.sport_id)
            if source is None or not source.is_active or source.slug != slug:
                raise ValueError("Team source is inactive or inconsistent")
            if sport is None or not sport.is_active:
                raise ValueError("Team sport is inactive or absent")
            validate_player_identity_text(team.external_id, 160)
            try:
                provider = self.registry.get(slug)
            except KeyError:
                raise ValueError("Team provider is not registered") from None
            if provider.slug != slug or not all(
                callable(getattr(provider, method, None))
                for method in ("fetch_team_player_ids", "fetch_player_identity")
            ):
                raise ValueError("Team provider is inconsistent or unsupported")
            if not isinstance(provider, PlayerIdentityProvider):
                raise ValueError("Provider does not implement player identity methods")
            validated.append((target, team, source, sport, provider))

        result = PlayerIdentityDiscoveryResult()
        # A source-owned ID cannot acquire different sports within the same run.
        players: dict[tuple[uuid.UUID, str], uuid.UUID] = {}
        seen_teams = set()
        for target, team, source, sport, provider in validated:
            if team.id in seen_teams:
                continue
            seen_teams.add(team.id)
            try:
                ids = await provider.fetch_team_player_ids(
                    team_external_id=team.external_id,
                    reference_date=reference_date,
                )
                if type(ids) is not tuple:
                    raise ValueError("Invalid player ID collection")
                for external_id in ids:
                    validate_player_identity_text(external_id, 160)
            except SQLAlchemyError:
                raise
            except Exception as exc:
                result.failures.append(
                    PlayerIdentityFailure(
                        target.provider_slug,
                        team.id,
                        None,
                        "provider_access_restricted"
                        if isinstance(exc, ProviderAccessRestrictedError)
                        else "team_discovery_failed",
                    )
                )
                continue
            result.teams_processed += 1
            for external_id in sorted(set(ids)):
                key = (source.id, external_id)
                if key in players:
                    if players[key] != sport.id:
                        result.failures.append(
                            PlayerIdentityFailure(
                                source.slug,
                                team.id,
                                external_id,
                                "player_sport_conflict",
                            )
                        )
                    continue
                players[key] = sport.id
                result.players_discovered += 1
                try:
                    identity = await provider.fetch_player_identity(athlete_external_id=external_id)
                    validate_player_identity(identity)
                    if identity.external_id != external_id:
                        raise ValueError("Player identity does not match request")
                except SQLAlchemyError:
                    raise
                except Exception as exc:
                    result.failures.append(
                        PlayerIdentityFailure(
                            source.slug,
                            team.id,
                            external_id,
                            "provider_access_restricted"
                            if isinstance(exc, ProviderAccessRestrictedError)
                            else "player_identity_failed",
                        )
                    )
                    continue
                try:
                    async with self.session.begin_nested():
                        existing = await self.session.scalar(
                            select(SportsCompetitor)
                            .where(
                                SportsCompetitor.source_id == source.id,
                                SportsCompetitor.external_id == external_id,
                            )
                            .with_for_update()
                        )
                        if existing is not None:
                            if (
                                existing.sport_id != sport.id
                                or existing.competitor_type != "athlete"
                            ):
                                raise ValueError("Existing provider identity conflicts with player")
                            if existing.canonical_competitor_id is not None:
                                canonical = await self.session.get(
                                    SportsCanonicalCompetitor,
                                    existing.canonical_competitor_id,
                                )
                                expected_key = build_canonical_competitor_key(
                                    sport.slug,
                                    "athlete",
                                    identity.name,
                                    None,
                                    source_slug=source.slug,
                                    external_id=external_id,
                                )
                                if (
                                    canonical is None
                                    or canonical.canonical_key != expected_key
                                    or canonical.identity_scope != "provider_scoped"
                                    or canonical.sport_id != sport.id
                                    or canonical.competitor_type != "athlete"
                                ):
                                    raise ValueError(
                                        "Existing canonical identity must not be replaced"
                                    )
                        await self.repository.upsert_competitor(
                            source_id=source.id,
                            sport_id=sport.id,
                            participant=ProviderParticipant(
                                external_id=identity.external_id,
                                name=identity.name,
                                competitor_type="athlete",
                                country_code=None,
                            ),
                            fetched_at=identity.fetched_at,
                        )
                        await self.session.flush()
                except ValueError:
                    result.failures.append(
                        PlayerIdentityFailure(
                            source.slug,
                            team.id,
                            external_id,
                            "ingestion_validation_failed",
                        )
                    )
                    continue
                result.players_processed += 1
        return result
