"""Opaque identities and strict, lossless multisport JSON contracts."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.sms24.providers.player_statistics import (
    ProviderPlayerStatistic,
    ProviderPlayerStatisticsResult,
    build_player_statistic_observation_key,
)


def test_identity_uses_only_opaque_record_not_facts():
    row = ProviderPlayerStatistic(athlete_external_id="p", record_reference="opaque:record")
    key = build_player_statistic_observation_key(row)
    assert key == build_player_statistic_observation_key(
        replace(
            row,
            athlete_external_id="other",
            athlete_name="Other",
            scope="fixture",
            fixture_external_id="f",
            period_label="period 2",
            metrics={"distance": 0},
            source_updated_at=datetime.now(UTC),
        )
    )
    assert key != build_player_statistic_observation_key(replace(row, external_id="opaque:record"))
    assert len(key) <= 100


@pytest.mark.parametrize(
    "changes",
    [
        {"external_id": None},
        {"external_id": ""},
        {"athlete_external_id": True},
        {"athlete_external_id": " "},
        {"fixture_external_id": 10},
        {"record_reference": ""},
        {"scope": "verified"},
        {"period_label": "x" * 101},
        {"source_updated_at": datetime(2026, 9, 21)},
        {"metrics": []},
        {"metadata": None},
        {"metrics": {1: 2}},
        {"metrics": {"a": (1, 2)}},
        {"metrics": {"a": float("nan")}},
        {"metadata": {"nested": {"a": float("inf")}}},
        {"metrics": {"a": "\x00"}},
    ],
)
def test_invalid_provider_data_rejected(changes):
    with pytest.raises(ValueError):
        ProviderPlayerStatistic(**{"athlete_external_id": "p", "external_id": "r", **changes})


def test_multisport_unknown_zero_and_result_validation():
    row = ProviderPlayerStatistic(
        athlete_external_id="p",
        external_id="r",
        metrics={"time_seconds": None, "points": 0, "sets": [6, 4]},
    )
    assert "goals" not in row.metrics
    assert row.metrics["time_seconds"] is None and row.metrics["points"] == 0
    result = ProviderPlayerStatisticsResult(fetched_at=datetime.now(UTC), statistics=(row,))
    assert result.statistics == (row,)
    assert ProviderPlayerStatisticsResult(fetched_at=datetime.now(UTC)).statistics == ()
    for values in ({"fetched_at": None}, {"statistics": [row]}, {"statistics": (None,)}):
        with pytest.raises(ValueError):
            ProviderPlayerStatisticsResult(**{"fetched_at": datetime.now(UTC), **values})
