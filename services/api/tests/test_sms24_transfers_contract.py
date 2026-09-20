"""Conservative provider transfer identity, unknown facts, and optional extension."""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.sms24.providers.base import SportsDataProvider
from app.sms24.providers.transfers import (
    ProviderTransfer,
    ProviderTransfersResult,
    build_transfer_observation_key,
)


def test_provider_identity_is_opaque_and_not_derived_from_transfer_facts():
    first = ProviderTransfer(athlete_external_id="player", external_id="Event/A")
    key = build_transfer_observation_key(first)
    assert key == build_transfer_observation_key(
        replace(
            first,
            athlete_name="Renamed",
            reported_date=date(2026, 9, 16),
            reported_type="Loan",
            from_team_name="Club",
            metadata={"fee": None},
        )
    )
    assert key != build_transfer_observation_key(replace(first, external_id="event/a"))
    assert key != build_transfer_observation_key(
        replace(first, external_id=None, record_reference="Event/A")
    )
    assert build_transfer_observation_key(
        replace(first, external_id=None, record_reference="r1")
    ) != (build_transfer_observation_key(replace(first, external_id=None, record_reference="r2")))


def test_unknown_facts_remain_unknown_and_contract_is_backward_compatible():
    transfer = ProviderTransfer(athlete_external_id="player", record_reference="stable-locator")
    assert transfer.reported_date is None
    assert transfer.reported_type is None
    assert transfer.from_team_external_id is None
    assert transfer.to_team_name is None
    assert transfer.athlete_name is None
    assert transfer.metadata == {}
    assert "fetch_transfers" not in SportsDataProvider.__abstractmethods__
    assert ProviderTransfersResult(fetched_at=datetime.now(UTC), transfers=(transfer,)).transfers


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"external_id": " "},
        {"record_reference": ""},
        {"external_id": "e", "athlete_external_id": ""},
        {"external_id": "e", "reported_date": datetime.now(UTC)},
        {"external_id": "e", "source_updated_at": datetime(2026, 1, 1)},
        {"external_id": "e", "metadata": {"bad": float("nan")}},
        {"external_id": "e", "metadata": []},
    ],
)
def test_invalid_transfer_contract(values):
    with pytest.raises(ValueError):
        ProviderTransfer(**{"athlete_external_id": "player", **values})


def test_fetch_timestamp_requires_timezone():
    with pytest.raises(ValueError):
        ProviderTransfersResult(fetched_at=datetime(2026, 1, 1))
