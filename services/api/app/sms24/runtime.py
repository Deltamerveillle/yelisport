"""Runtime assembly for SMS24 provider ingestion."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.sms24.ingestion import (
    SMS24IngestionRepository,
    SMS24IngestionService,
)
from app.sms24.providers.api_football import APIFootballProvider
from app.sms24.providers.espn import ESPNProvider
from app.sms24.providers.registry import ProviderRegistry
from app.sms24.providers.sportmonks import SportmonksProvider
from app.sms24.runner import (
    SMS24ProviderRunner,
    SMS24RunnerRepository,
)
from app.sms24.standings import SMS24StandingsRepository, StandingsIngestionService
from app.sms24.standings_runner import StandingsProviderRunner
from app.sms24.transfers_batch import (
    AutomaticTransfersCursor,
    AutomaticTransfersResult,
    TransfersBatchOrchestrator,
)
from app.sms24.transfers_runner import TransfersRunner
from app.sms24.transfers_targets import SportmonksTransfersTargetDiscovery


def build_sms24_provider_registry(
    settings: Settings | None = None,
) -> ProviderRegistry:
    """Build the provider registry from runtime configuration."""

    settings = settings or get_settings()
    registry = ProviderRegistry()

    api_football_key = settings.sms24_api_football_key

    if api_football_key and api_football_key.strip():
        registry.register(
            APIFootballProvider(
                api_key=api_football_key,
            )
        )

    sportmonks_key = settings.sms24_sportmonks_key
    if sportmonks_key and sportmonks_key.strip():
        registry.register(SportmonksProvider(api_key=sportmonks_key))

    if settings.sms24_espn_enabled:
        registry.register(ESPNProvider())

    return registry


def build_sms24_runner(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
) -> SMS24ProviderRunner:
    """Assemble the SMS24 runner around one database session."""

    registry = build_sms24_provider_registry(settings)

    ingestion_repository = SMS24IngestionRepository(
        session
    )
    ingestion_service = SMS24IngestionService(
        ingestion_repository
    )

    runner_repository = SMS24RunnerRepository(
        session
    )

    return SMS24ProviderRunner(
        registry=registry,
        repository=runner_repository,
        ingestion_service=ingestion_service,
    )


def build_sms24_standings_runner(
    session: AsyncSession, *, settings: Settings | None = None,
) -> StandingsProviderRunner:
    """Assemble standings providers using the existing settings/credential registry."""
    return StandingsProviderRunner(
        session=session,
        registry=build_sms24_provider_registry(settings),
        ingestion_service=StandingsIngestionService(SMS24StandingsRepository(session)),
    )


def build_sms24_transfers_runner(
    session: AsyncSession, *, settings: Settings | None = None,
) -> TransfersRunner:
    """Reuse local registration without enabling Transfers support or capabilities."""
    return TransfersRunner(session=session, registry=build_sms24_provider_registry(settings))


async def run_sms24_automatic_transfers(
    session: AsyncSession, *, reference_date: date, settings: Settings | None = None,
    max_teams: int = 20, max_players: int = 100,
    cursor: AutomaticTransfersCursor | None = None,
) -> AutomaticTransfersResult:
    """Discover ephemeral targets then ingest, without committing or scheduling work."""
    if cursor is not None and not isinstance(cursor, AutomaticTransfersCursor):
        raise ValueError("Invalid automatic Transfers cursor")
    cursor = cursor or AutomaticTransfersCursor()
    registry = build_sms24_provider_registry(settings)
    discovery = SportmonksTransfersTargetDiscovery(
        session=session, registry=registry, max_teams=max_teams,
    )
    batch = TransfersBatchOrchestrator(
        runner=TransfersRunner(session=session, registry=registry), max_players=max_players,
    )
    targets = await discovery.discover(
        reference_date=reference_date, after_team_external_id=cursor.after_team_external_id,
    )
    result = await batch.run(
        player_ids=targets.player_ids, after_player_external_id=cursor.after_player_external_id,
    )
    next_cursor = None
    if result.has_more:
        next_cursor = AutomaticTransfersCursor(cursor.after_team_external_id, result.next_cursor)
    elif targets.has_more:
        next_cursor = AutomaticTransfersCursor(targets.next_cursor)
    return AutomaticTransfersResult(discovery=targets, batch=result, next_cursor=next_cursor)
