"""Optional transfer contract; existing SportsDataProvider implementations stay valid.

Adapters must supply either an opaque event ID or a stable provider record reference
(e.g. a documented record locator). Never derive identity from names/dates/teams or
list positions. Switching identity strategies later requires explicit reconciliation.
Only explicit adapter support plus the existing transfers capability enables fetching.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol


def _text(value: str | None, limit: int, *, required: bool = False) -> None:
    if value is None and not required:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("Transfer text/identifier is missing or exceeds its limit")


def _timestamp(value: datetime | None, *, required: bool = False) -> None:
    if value is None and not required:
        return
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Transfer timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderTransfer:
    athlete_external_id: str
    athlete_name: str | None = None
    external_id: str | None = None
    record_reference: str | None = None
    from_team_external_id: str | None = None
    from_team_name: str | None = None
    to_team_external_id: str | None = None
    to_team_name: str | None = None
    reported_date: date | None = None
    reported_type: str | None = None
    source_updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_transfer(self)


def validate_transfer(transfer: ProviderTransfer) -> None:
    _text(transfer.athlete_external_id, 160, required=True)
    for name in ("external_id", "from_team_external_id", "to_team_external_id"):
        _text(getattr(transfer, name), 160)
    for name in ("athlete_name", "from_team_name", "to_team_name", "reported_type"):
        _text(getattr(transfer, name), 200)
    _text(transfer.record_reference, 500, required=transfer.external_id is None)
    if transfer.reported_date is not None and type(transfer.reported_date) is not date:
        raise ValueError("Transfer date must be a date, or unknown")
    _timestamp(transfer.source_updated_at)
    if not isinstance(transfer.metadata, dict):
        raise ValueError("Transfer metadata must be a JSON object")
    try:
        json.dumps(transfer.metadata, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Transfer metadata must be JSON serializable") from exc


def build_transfer_observation_key(transfer: ProviderTransfer) -> str:
    validate_transfer(transfer)
    parts = (
        ["external_id", transfer.external_id]
        if transfer.external_id is not None
        else ["record_reference", transfer.record_reference or ""]
    )
    return (
        "sms24:transfer:"
        + hashlib.sha256(
            json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderTransfersResult:
    fetched_at: datetime
    transfers: tuple[ProviderTransfer, ...] = ()

    def __post_init__(self) -> None:
        _timestamp(self.fetched_at, required=True)
        for transfer in self.transfers:
            validate_transfer(transfer)


class TransfersProvider(Protocol):
    """Optional structural extension, not a new abstract requirement or registry."""

    async def fetch_transfers(self, *, athlete_external_id: str) -> ProviderTransfersResult: ...
