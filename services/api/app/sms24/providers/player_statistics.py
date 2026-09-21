"""Multisport provider facts, with opaque stable record identity and no human identity."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


def _text(value: str | None, limit: int, *, required: bool = False) -> None:
    if value is None and not required:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise ValueError("Invalid statistics text or opaque identifier")


def validate_statistics_timestamp(value: datetime | None, *, required: bool = False) -> None:
    if value is None and not required:
        return
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Statistics timestamp must be timezone-aware")


def _json_object(value: Any) -> None:
    if type(value) is not dict:
        raise ValueError("Statistics JSON must be an object")
    try:
        json.dumps(value, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("Statistics JSON must contain finite JSON values") from exc

    def check(item):
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str or "\x00" in key:
                    raise ValueError("Statistics JSON keys must be strings")
                check(child)
        elif type(item) is list:
            for child in item:
                check(child)
        elif type(item) not in (str, bool, int, float, type(None)):
            raise ValueError("Statistics JSON values must not require coercion")
        elif isinstance(item, str) and "\x00" in item:
            raise ValueError("Statistics JSON strings must be PostgreSQL-compatible")

    check(value)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderPlayerStatistic:
    athlete_external_id: str
    external_id: str | None = None
    record_reference: str | None = None
    athlete_name: str | None = None
    fixture_external_id: str | None = None
    scope: str = "unknown"
    period_label: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_updated_at: datetime | None = None

    def __post_init__(self) -> None:
        validate_player_statistic(self)


def validate_player_statistic(value: ProviderPlayerStatistic) -> None:
    if not isinstance(value, ProviderPlayerStatistic):
        raise ValueError("A provider player statistic is required")
    _text(value.athlete_external_id, 160, required=True)
    _text(value.external_id, 160)
    _text(value.record_reference, 500, required=value.external_id is None)
    _text(value.athlete_name, 200)
    _text(value.fixture_external_id, 160)
    _text(value.period_label, 100)
    if value.scope not in ("unknown", "fixture", "season", "competition", "career", "other"):
        raise ValueError("Invalid statistics scope")
    validate_statistics_timestamp(value.source_updated_at)
    _json_object(value.metrics)
    _json_object(value.metadata)


def build_player_statistic_observation_key(value: ProviderPlayerStatistic) -> str:
    validate_player_statistic(value)
    identity = (
        ["external_id", value.external_id]
        if value.external_id is not None
        else ["record_reference", value.record_reference]
    )
    encoded = json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sms24:player-statistic:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderPlayerStatisticsResult:
    fetched_at: datetime
    statistics: tuple[ProviderPlayerStatistic, ...] = ()

    def __post_init__(self) -> None:
        validate_player_statistics_result(self)


def validate_player_statistics_result(value: ProviderPlayerStatisticsResult) -> None:
    if not isinstance(value, ProviderPlayerStatisticsResult) or type(value.statistics) is not tuple:
        raise ValueError("Invalid provider statistics result")
    validate_statistics_timestamp(value.fetched_at, required=True)
    for statistic in value.statistics:
        validate_player_statistic(statistic)


class PlayerStatisticsProvider(Protocol):
    async def fetch_player_statistics(
        self,
        *,
        athlete_external_id: str,
    ) -> ProviderPlayerStatisticsResult: ...
