"""Strict row normalization for the audited standings payloads; no derived scores."""

from dataclasses import fields
from datetime import datetime
from typing import Any

from app.sms24.providers.base import ProviderParticipant
from app.sms24.providers.standings import ProviderStanding

SPORTMONKS_DETAIL_FIELDS = {
    129: "played",
    130: "wins",
    131: "draws",
    132: "losses",
    133: "goals_for",
    134: "goals_against",
    135: "home_played",
    136: "home_wins",
    137: "home_draws",
    138: "home_losses",
    139: "home_goals_for",
    140: "home_goals_against",
    141: "away_played",
    142: "away_wins",
    143: "away_draws",
    144: "away_losses",
    145: "away_goals_for",
    146: "away_goals_against",
    179: "goal_difference",
    185: "home_points",
    186: "away_points",
    187: "points",
}


def _object(value: Any, field: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Standings {field} must be an object")
    return value


def _integer(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if type(value) is int:
        return value
    if isinstance(value, str) and value.lstrip("-").isascii() and value.lstrip("-").isdigit():
        try:
            return int(value)
        except ValueError:
            pass
    raise ValueError(f"Standings {field} must be an integer")


def _text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Standings {field} must be text")
    return value


def _identifier(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError(f"Standings {field} requires a nonempty provider identifier")
    return value  # Opaque, including case and punctuation.


def _timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Standings update must be an ISO timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Standings update must be timezone-aware")
    return parsed


def validate_standing(row: ProviderStanding) -> None:
    """Also validate normalized contracts submitted directly to ingestion."""
    if type(row.position) is not int or row.position < 1:
        raise ValueError("Standings position must be a positive integer")
    _identifier(row.participant.external_id, "participant id", required=True)
    if not isinstance(row.participant.name, str) or not row.participant.name.strip():
        raise ValueError("Standings participant name is required")
    for field in fields(row):
        value = getattr(row, field.name)
        if field.type == int | None and value is not None and type(value) is not int:
            raise ValueError(f"Standings {field.name} must be an integer")
        if (
            field.name == "external_id"
            or field.name.endswith("_external_id")
            or field.name
            in {
                "external_competition_id",
                "external_season_id",
            }
        ):
            _identifier(value, field.name)
    for field, limit in (
        ("form", 200),
        ("movement_status", 80),
        ("group_name", 240),
        ("description", None),
    ):
        value = _text(getattr(row, field), field)
        if value is not None and limit is not None and len(value) > limit:
            raise ValueError(f"Standings {field} exceeds {limit} characters")
    if row.provider_updated_at is not None and (
        row.provider_updated_at.tzinfo is None or row.provider_updated_at.utcoffset() is None
    ):
        raise ValueError("Standings provider_updated_at must be timezone-aware")


def normalize_api_football_standing(item: Any) -> ProviderStanding:
    item = _object(item, "row")
    team = _object(item.get("team"), "team")
    row = ProviderStanding(
        participant=ProviderParticipant(
            external_id=_identifier(team.get("id"), "team.id", required=True),
            name=_text(team.get("name"), "team.name"),
            logo_url=_text(team.get("logo"), "team.logo"),
        ),
        position=_integer(item.get("rank"), "rank"),
        points=_integer(item.get("points"), "points"),
        goal_difference=_integer(item.get("goalsDiff"), "goalsDiff"),
        group_name=_text(item.get("group"), "group"),
        form=_text(item.get("form"), "form"),
        movement_status=_text(item.get("status"), "status"),
        description=_text(item.get("description"), "description"),
        provider_updated_at=_timestamp(item.get("update")),
    )
    for section, prefix in (("all", ""), ("home", "home_"), ("away", "away_")):
        stats = _object(item.get(section), section)
        for raw, normalized in (
            ("played", "played"),
            ("win", "wins"),
            ("draw", "draws"),
            ("lose", "losses"),
        ):
            setattr(row, prefix + normalized, _integer(stats.get(raw), f"{section}.{raw}"))
        goals = _object(stats.get("goals"), f"{section}.goals")
        for raw, normalized in (("for", "goals_for"), ("against", "goals_against")):
            setattr(row, prefix + normalized, _integer(goals.get(raw), f"{section}.goals.{raw}"))
    # No standing ID, stage/group IDs or home/away points are supplied by this contract.
    validate_standing(row)
    return row


def normalize_sportmonks_standing(item: Any) -> ProviderStanding:
    item = _object(item, "row")
    participant = _object(item.get("participant"), "participant")
    participant_id = _identifier(item.get("participant_id"), "participant_id", required=True)
    embedded_id = _identifier(participant.get("id"), "participant.id")
    if embedded_id is not None and embedded_id != participant_id:
        raise ValueError("Standings participant identifiers disagree")
    rule = _object(item.get("rule"), "rule")
    rule_type = _object(rule.get("type"), "rule.type")
    group = _object(item.get("group"), "group")
    row = ProviderStanding(
        external_id=_identifier(item.get("id"), "id", required=True),
        external_competition_id=_identifier(item.get("league_id"), "league_id", required=True),
        external_season_id=_identifier(item.get("season_id"), "season_id", required=True),
        participant=ProviderParticipant(
            external_id=participant_id,
            name=_text(participant.get("name"), "participant.name"),
            logo_url=_text(participant.get("image_path"), "participant.image_path"),
        ),
        position=_integer(item.get("position"), "position"),
        points=_integer(item.get("points"), "points"),
        movement_status=_text(item.get("result"), "result"),
        description=_text(rule_type.get("name"), "rule.type.name"),
        group_name=_text(group.get("name"), "group.name"),
    )
    for name in ("stage", "group", "round", "standing_rule"):
        setattr(row, f"{name}_external_id", _identifier(item.get(f"{name}_id"), f"{name}_id"))
    details = item.get("details")
    if details is None:
        details = []
    if not isinstance(details, list):
        raise ValueError("Standings details must be a list")
    seen = {}
    for detail in details:
        detail = _object(detail, "detail")
        type_id = detail.get("type_id")
        if isinstance(type_id, str) and type_id.isascii() and type_id.isdigit():
            type_id = int(type_id)
        field = SPORTMONKS_DETAIL_FIELDS.get(type_id) if type(type_id) is int else None
        if field is None:
            continue
        value = _integer(detail.get("value"), f"detail {type_id}")
        if field in seen and seen[field] != value:
            raise ValueError(f"Conflicting standings detail {type_id}")
        seen[field] = value
        if field == "points" and row.points is not None:
            if value is not None and row.points != value:
                raise ValueError("Conflicting standings points")
        else:
            setattr(row, field, value)
    validate_standing(row)
    return row
