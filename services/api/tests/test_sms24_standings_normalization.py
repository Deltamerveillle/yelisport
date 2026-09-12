"""Audited provider standings contracts, without network requests."""

from datetime import datetime

import pytest

from app.sms24.providers.api_football import APIFootballProvider
from app.sms24.providers.sportmonks import SportmonksProvider


def api_row():
    return {
        "rank": 2,
        "team": {"id": 42, "name": "Arsenal", "logo": "https://example.test/a.png"},
        "points": 9,
        "goalsDiff": -2,
        "group": "Group A",
        "form": "WLWDW",
        "status": "up",
        "description": "Qualification",
        "update": "2026-09-11T12:00:00+02:00",
        "all": {"played": 5, "win": 3, "draw": 0, "lose": 2, "goals": {"for": 6, "against": 8}},
        "home": {"played": 2, "win": 2, "draw": 0, "lose": 0, "goals": {"for": 4, "against": 0}},
        "away": {"played": 3, "win": 1, "draw": 0, "lose": 2, "goals": {"for": 2, "against": 8}},
    }


def sportmonks_row():
    return {
        "id": 123,
        "participant_id": 42,
        "league_id": 7,
        "season_id": 88,
        "stage_id": "stage:A",
        "group_id": "g/1",
        "round_id": 9,
        "standing_rule_id": 4,
        "position": 1,
        "result": "up",
        "points": None,
        "participant": {"id": 42, "name": "Arsenal", "image_path": "https://example.test/a.png"},
        "details": [],
        "rule": {
            "id": 137697,
            "model_type": "stage",
            "model_id": 77482564,
            "type_id": 180,
            "position": 1,
            "type": {
                "id": 180,
                "name": "UEFA Champions League",
                "code": "uefa-champions-league",
                "developer_name": "UEFA_CHAMPIONS_LEAGUE",
            },
        },
        "group": {"name": "Group A"},
    }


def test_api_football_maps_only_explicit_values():
    row = APIFootballProvider.normalize_standing(api_row())
    assert row.participant.external_id == "42" and row.participant.name == "Arsenal"
    assert row.participant.country_code is None
    assert (row.position, row.points, row.goal_difference) == (2, 9, -2)
    assert (row.played, row.wins, row.draws, row.losses, row.goals_for, row.goals_against) == (
        5,
        3,
        0,
        2,
        6,
        8,
    )
    assert (
        row.home_played,
        row.home_wins,
        row.home_draws,
        row.home_losses,
        row.home_goals_for,
        row.home_goals_against,
    ) == (2, 2, 0, 0, 4, 0)
    assert (
        row.away_played,
        row.away_wins,
        row.away_draws,
        row.away_losses,
        row.away_goals_for,
        row.away_goals_against,
    ) == (3, 1, 0, 2, 2, 8)
    assert row.home_points is None and row.away_points is None
    assert (row.group_name, row.form, row.movement_status, row.description) == (
        "Group A",
        "WLWDW",
        "up",
        "Qualification",
    )
    assert (
        row.group_external_id is None and row.stage_external_id is None and row.external_id is None
    )
    assert row.provider_updated_at == datetime.fromisoformat("2026-09-11T12:00:00+02:00")


def test_absent_api_stats_stay_unknown_not_zero_or_derived():
    row = APIFootballProvider.normalize_standing(
        {"rank": 1, "team": {"id": "A/42", "name": "Team"}}
    )
    assert row.points is None and row.played is None and row.goal_difference is None
    assert row.home_wins is None and row.away_goals_for is None
    assert row.provider_updated_at is None and row.participant.external_id == "A/42"


@pytest.mark.parametrize(
    ("detail_id", "field"),
    [
        (129, "played"),
        (130, "wins"),
        (131, "draws"),
        (132, "losses"),
        (133, "goals_for"),
        (134, "goals_against"),
        (135, "home_played"),
        (136, "home_wins"),
        (137, "home_draws"),
        (138, "home_losses"),
        (139, "home_goals_for"),
        (140, "home_goals_against"),
        (141, "away_played"),
        (142, "away_wins"),
        (143, "away_draws"),
        (144, "away_losses"),
        (145, "away_goals_for"),
        (146, "away_goals_against"),
        (179, "goal_difference"),
        (185, "home_points"),
        (186, "away_points"),
        (187, "points"),
    ],
)
def test_every_audited_sportmonks_detail_mapping(detail_id, field):
    data = sportmonks_row()
    data["details"] = [{"type_id": detail_id, "value": str(detail_id)}]
    row = SportmonksProvider.normalize_standing(data)
    assert getattr(row, field) == detail_id


def test_sportmonks_preserves_context_and_ignores_unknown_details():
    data = sportmonks_row()
    data["points"] = 0
    data["details"] = [
        {"type_id": 999999, "value": {"unknown": "shape"}},
        {"type_id": 179, "value": -4},
    ]
    row = SportmonksProvider.normalize_standing(data)
    assert (
        row.external_id == "123"
        and row.external_season_id == "88"
        and row.external_competition_id == "7"
    )
    assert row.participant.external_id == "42" and row.participant.country_code is None
    assert (
        row.stage_external_id,
        row.group_external_id,
        row.round_external_id,
        row.standing_rule_external_id,
    ) == ("stage:A", "g/1", "9", "4")
    assert (row.group_name, row.description, row.movement_status) == (
        "Group A",
        "UEFA Champions League",
        "up",
    )
    assert row.points == 0 and row.goal_difference == -4
    assert row.home_points is None and row.away_points is None
    assert row.provider_updated_at is None and row.form is None


@pytest.mark.parametrize("field", ["id", "participant_id", "league_id", "season_id", "position"])
def test_sportmonks_requires_identifiers_and_position(field):
    data = sportmonks_row()
    del data[field]
    with pytest.raises(ValueError):
        SportmonksProvider.normalize_standing(data)


@pytest.mark.parametrize("position", [None, 0, -1, True, 1.5, "first"])
@pytest.mark.parametrize("provider", ["api", "sportmonks"])
def test_invalid_positions_are_rejected(provider, position):
    data = api_row() if provider == "api" else sportmonks_row()
    data["rank" if provider == "api" else "position"] = position
    normalize = (
        APIFootballProvider.normalize_standing
        if provider == "api"
        else SportmonksProvider.normalize_standing
    )
    with pytest.raises(ValueError):
        normalize(data)


def test_conflicting_sportmonks_identity_and_totals_fail_conservatively():
    data = sportmonks_row()
    data["participant"]["id"] = 9419
    with pytest.raises(ValueError, match="identifiers disagree"):
        SportmonksProvider.normalize_standing(data)
    data = sportmonks_row()
    data["points"] = 4
    data["details"] = [{"type_id": 187, "value": 5}]
    with pytest.raises(ValueError, match="Conflicting"):
        SportmonksProvider.normalize_standing(data)


def test_naive_update_is_not_given_an_invented_timezone():
    data = api_row()
    data["update"] = "2026-09-11T12:00:00"
    with pytest.raises(ValueError, match="timezone-aware"):
        APIFootballProvider.normalize_standing(data)


@pytest.mark.parametrize("rule", [None, {}, {"type": None}, {"type": {}}])
def test_missing_sportmonks_rule_type_does_not_invent_description(rule):
    data = sportmonks_row()
    if rule is None:
        data.pop("rule")
    else:
        data["rule"] = rule
    data["details"] = [{"type_id": 999999, "value": {"unknown": True}}]
    row = SportmonksProvider.normalize_standing(data)
    assert row.description is None
