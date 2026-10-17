"""Sequential bounded Transfers orchestration above the single-player runner."""

from collections.abc import Iterable
from dataclasses import dataclass

from app.sms24.providers.sportmonks import SportmonksProvider
from app.sms24.transfers_runner import TransfersAllProvidersFailed, TransfersRunner
from app.sms24.transfers_targets import TransfersTargetDiscoveryResult, validate_target_cursor


@dataclass(frozen=True, slots=True)
class TransfersTargetAttempt:
    athlete_external_id: str
    success: bool
    observations_processed: int = 0
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class TransfersBatchResult:
    targets_discovered: int
    attempts: tuple[TransfersTargetAttempt, ...]
    targets_before_cursor: int = 0
    next_cursor: str | None = None

    @property
    def has_more(self) -> bool:
        return self.next_cursor is not None

    @property
    def targets_attempted(self) -> int:
        return len(self.attempts)

    @property
    def targets_succeeded(self) -> int:
        return sum(attempt.success for attempt in self.attempts)

    @property
    def targets_failed(self) -> int:
        return self.targets_attempted - self.targets_succeeded

    @property
    def targets_deferred(self) -> int:
        return self.targets_discovered - self.targets_before_cursor - self.targets_attempted

    @property
    def observations_processed(self) -> int:
        return sum(attempt.observations_processed for attempt in self.attempts)


@dataclass(frozen=True, slots=True)
class AutomaticTransfersCursor:
    after_team_external_id: str | None = None
    after_player_external_id: str | None = None

    def __post_init__(self) -> None:
        validate_target_cursor(self.after_team_external_id)
        validate_target_cursor(self.after_player_external_id)


@dataclass(frozen=True, slots=True)
class AutomaticTransfersResult:
    discovery: TransfersTargetDiscoveryResult
    batch: TransfersBatchResult
    next_cursor: AutomaticTransfersCursor | None = None


class TransfersBatchOrchestrator:
    """Continue on sanitized runner failures; unexpected errors (including SQL) propagate.

    The caller retains transaction ownership. The runner already isolates each
    ingestion attempt with a savepoint. No target is treated as a human identity.
    """

    def __init__(self, *, runner: TransfersRunner, max_players: int = 100) -> None:
        if type(max_players) is not int or max_players < 1:
            raise ValueError("max_players must be a positive integer")
        self.runner = runner
        self.max_players = max_players

    async def run(
        self,
        *,
        player_ids: Iterable[str],
        after_player_external_id: str | None = None,
    ) -> TransfersBatchResult:
        validate_target_cursor(after_player_external_id)
        if isinstance(player_ids, str | bytes):
            raise ValueError("Supply a collection of player identifiers")
        players = set()
        for player_id in player_ids:
            if not isinstance(player_id, str):
                raise ValueError("Player identifiers must be strings")
            SportmonksProvider._transfer_id(player_id)
            players.add(player_id)
        remaining = sorted(
            player_id
            for player_id in players
            if after_player_external_id is None or player_id > after_player_external_id
        )
        attempts = []
        for player_id in remaining[: self.max_players]:
            try:
                result = await self.runner.run(targets={"sportmonks": player_id})
            except TransfersAllProvidersFailed:
                # Do not echo exception messages or upstream-derived attempt text.
                attempts.append(
                    TransfersTargetAttempt(
                        player_id,
                        False,
                        reason="transfers_target_failed",
                    )
                )
                continue
            attempts.append(
                TransfersTargetAttempt(
                    player_id,
                    True,
                    observations_processed=result.observations_processed,
                )
            )
        return TransfersBatchResult(
            targets_discovered=len(players),
            attempts=tuple(attempts),
            targets_before_cursor=len(players) - len(remaining),
            next_cursor=(
                remaining[self.max_players - 1] if len(remaining) > self.max_players else None
            ),
        )
