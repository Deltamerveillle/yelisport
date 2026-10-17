"""Transfers orchestration against isolated PostgreSQL, with HTTP forbidden."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.models.athlete import Athlete
from app.models.athlete_country_eligibility import AthleteCountryEligibility
from app.models.athlete_passport import AthletePassport
from app.models.sports_live import SportsDataSource, SportsDataSourceCapability
from app.models.sports_transfers import (
    SportsAthleteIdentityLink,
    SportsCanonicalTransfer,
    SportsTransferObservation,
)
from app.models.user import User
from app.sms24.providers.base import ProviderHealthResult, SportsDataProvider
from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.registry import ProviderRegistry
from app.sms24.providers.transfers import ProviderTransfer, ProviderTransfersResult
from app.sms24.transfers import SMS24TransfersRepository
from app.sms24.transfers_runner import TransfersAllProvidersFailed, TransfersRunner
from tests import test_sms24_transfers_postgres as foundation
from tests.test_sms24_transfers_postgres import NOW, add

connection = foundation.connection
session = foundation.session


@pytest.fixture(autouse=True)
def forbid_http(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("Real HTTP is forbidden")
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)
    monkeypatch.setattr(httpx.Client, "send", lambda *a, **k: pytest.fail("HTTP forbidden"))
    for method in ("create_event", "resolve_observation", "link_athlete"):
        monkeypatch.setattr(SMS24TransfersRepository, method, forbidden)


class FakeProvider(SportsDataProvider):
    name = "Fake Transfers"

    def __init__(self, slug):
        self.slug = slug
        self.check_health = AsyncMock(return_value=ProviderHealthResult(True, NOW))
        self.fetch_transfers = AsyncMock(return_value=ProviderTransfersResult(
            fetched_at=NOW,
            transfers=(ProviderTransfer(athlete_external_id="player", external_id="event"),),
        ))

    async def check_health(self):
        raise AssertionError("Replaced by mock")

    async def fetch_fixtures(self, **kwargs):
        pytest.fail("Fixtures must never be fetched")


async def setup(session, slugs=("one", "two")):
    registry = ProviderRegistry()
    for index, slug in enumerate(slugs):
        source = await add(session, SportsDataSource, slug=slug, name=slug,
                           priority=100-index, health_status="degraded",
                           last_checked_at=NOW, last_failure_at=NOW, last_success_at=NOW)
        await add(session, SportsDataSourceCapability, source_id=source.id,
                  capability="transfers", priority=index)
        registry.register(FakeProvider(slug))
    return TransfersRunner(session=session, registry=registry)


async def rows(session):
    return list(await session.scalars(select(SportsTransferObservation)))


async def snapshot(session, models):
    return [(await session.execute(select(model.__table__).order_by(model.id))).mappings().all()
            for model in models]


@pytest.mark.parametrize("state", ["absent", "inactive", "source_inactive", "unknown"])
async def test_ineligible_targets_never_probe_or_activate(session, state):
    runner = await setup(session, ("one",))
    cap = await session.scalar(select(SportsDataSourceCapability).where(
        SportsDataSourceCapability.capability == "transfers"))
    if state == "absent":
        await session.delete(cap)
    elif state == "inactive":
        cap.is_active = False
    elif state == "source_inactive":
        source = await session.get(SportsDataSource, cap.source_id)
        source.is_active = False
    await session.flush()
    before = await snapshot(session, [SportsDataSource, SportsDataSourceCapability])
    with pytest.raises(TransfersAllProvidersFailed) as caught:
        await runner.run(targets={"unknown" if state == "unknown" else "one": "player"})
    assert caught.value.attempts[0].reason == "transfers_capability_not_active"
    runner.registry.get("one").check_health.assert_not_awaited()
    runner.registry.get("one").fetch_transfers.assert_not_awaited()
    assert before == await snapshot(session, [SportsDataSource, SportsDataSourceCapability])


@pytest.mark.parametrize("outcome,reason", [
    ("missing", "provider_not_registered"),
    ("unsupported", "transfers_not_supported"),
    ("noncallable", "transfers_not_supported"),
    ("health_invalid", "health_check_failed"),
    ("unhealthy", "health_check_failed"),
    ("health_error", "health_check_failed"),
    ("health_restricted", "provider_access_restricted"),
    ("fetch_restricted", "provider_access_restricted"),
    ("fetch_error", "fetch_or_payload_failed"),
    ("result_invalid", "fetch_or_payload_failed"),
    ("row_invalid", "fetch_or_payload_failed"),
    ("timestamp_invalid", "fetch_or_payload_failed"),
    ("collection_invalid", "fetch_or_payload_failed"),
    ("metadata_invalid", "fetch_or_payload_failed"),
    ("wrong_player", "fetch_or_payload_failed"),
    ("empty", None), ("success", None),
])
async def test_outcomes_aggregate_and_preserve_health(session, outcome, reason):
    runner = await setup(session)
    provider = runner.registry.get("one")
    fetch = provider.fetch_transfers
    if outcome == "missing":
        other = runner.registry.get("two")
        runner.registry.clear()
        runner.registry.register(other)
    elif outcome == "unsupported":
        del provider.fetch_transfers
    elif outcome == "noncallable":
        provider.fetch_transfers = None
    elif outcome == "health_invalid":
        provider.check_health.return_value = {"is_healthy": True}
    elif outcome == "unhealthy":
        provider.check_health.return_value = ProviderHealthResult(False, NOW)
    elif outcome in ("health_error", "health_restricted"):
        provider.check_health.side_effect = (ProviderAccessRestrictedError()
            if outcome.endswith("restricted") else RuntimeError("secret https://private body"))
    elif outcome in ("fetch_error", "fetch_restricted"):
        fetch.side_effect = (ProviderAccessRestrictedError()
            if outcome.endswith("restricted") else RuntimeError("secret https://private body"))
    elif outcome == "result_invalid":
        fetch.return_value = {"secret": "body"}
    elif outcome in ("row_invalid", "timestamp_invalid", "collection_invalid"):
        result = fetch.return_value
        field, value = {"row_invalid": ("transfers", (object(),)),
                        "timestamp_invalid": ("fetched_at", NOW.replace(tzinfo=None)),
                        "collection_invalid": ("transfers", {})}[outcome]
        object.__setattr__(result, field, value)
    elif outcome == "metadata_invalid":
        fetch.return_value.transfers[0].metadata["bad"] = float("nan")
    elif outcome == "wrong_player":
        fetch.return_value = ProviderTransfersResult(fetched_at=NOW, transfers=(
            ProviderTransfer(athlete_external_id="other", external_id="event"),))
    elif outcome == "empty":
        fetch.return_value = ProviderTransfersResult(fetched_at=NOW)
    before = await snapshot(session, [SportsDataSource, SportsDataSourceCapability])
    result = await runner.run(targets={"two": "player", "one": "player"})
    assert [a.provider_slug for a in result.attempts] == ["one", "two"]
    assert result.attempts[0].reason == reason
    assert result.successes == (2 if reason is None else 1)
    assert result.failures == (0 if reason is None else 1)
    assert "secret" not in repr(result) and "https://" not in repr(result)
    if outcome in ("missing", "unsupported", "noncallable"):
        provider.check_health.assert_not_awaited()
        fetch.assert_not_awaited()
    runner.registry.get("two").fetch_transfers.assert_awaited_once_with(
        athlete_external_id="player")
    assert before == await snapshot(session, [SportsDataSource, SportsDataSourceCapability])


async def test_replay_stale_empty_and_no_graph_or_human_mutations(session):
    sport, _, node = await foundation.seed(session)
    person = await foundation.human(session, sport)
    await add(session, AthletePassport, athlete_id=person.id, club_name="Unchanged")
    await add(session, SportsAthleteIdentityLink, athlete_id=person.id,
              canonical_competitor_id=node.id, method="manual_review", status="documented",
              established_by="reviewer", evidence_reference="explicit")
    await add(session, SportsCanonicalTransfer, canonical_athlete_id=node.id)
    protected = [User, Athlete, AthletePassport, AthleteCountryEligibility,
                 SportsAthleteIdentityLink, SportsCanonicalTransfer]
    before = await snapshot(session, protected)
    runner = await setup(session)
    targets = {"one": "player", "two": "player"}
    result = await runner.run(targets=targets)
    assert result.observations_processed == 2
    ids = {row.id for row in await rows(session)}
    assert len(ids) == 2
    await runner.run(targets=targets)
    assert ids == {row.id for row in await rows(session)}
    provider = runner.registry.get("one")
    transfer = replace(provider.fetch_transfers.return_value.transfers[0], reported_type="raw")
    provider.fetch_transfers.return_value = ProviderTransfersResult(
        fetched_at=NOW+timedelta(days=1), transfers=(transfer,))
    await runner.run(targets={"one": "player"})
    provider.fetch_transfers.return_value = ProviderTransfersResult(
        fetched_at=NOW, transfers=(replace(transfer, reported_type=None),))
    await runner.run(targets={"one": "player"})
    assert sorted(row.reported_type or "" for row in await rows(session)) == ["", "raw"]
    provider.fetch_transfers.return_value = ProviderTransfersResult(fetched_at=NOW)
    assert (await runner.run(targets={"one": "player"})).observations_processed == 0
    assert ids == {row.id for row in await rows(session)}
    for row in await rows(session):
        assert row.canonical_transfer_id is row.athlete_competitor_id is None
        assert row.reported_date is row.from_team_external_id is row.to_team_external_id is None
    assert before == await snapshot(session, protected)


@pytest.mark.parametrize("bad_slug", ["one", "two"])
async def test_provider_batch_rolls_back_without_losing_other_provider(session, bad_slug):
    runner = await setup(session)
    source = await runner.repository.get_active_source_for_capability(bad_slug, "transfers")
    await runner.ingestion_repository.record_observation(source_id=source.id, fetched_at=NOW,
        transfer=ProviderTransfer(athlete_external_id="different", external_id="conflict"))
    runner.registry.get(bad_slug).fetch_transfers.return_value = ProviderTransfersResult(
        fetched_at=NOW, transfers=(
            ProviderTransfer(athlete_external_id="player", external_id="first"),
            ProviderTransfer(athlete_external_id="player", external_id="conflict")))
    result = await runner.run(targets={"one": "player", "two": "player"})
    assert result.successes == 1
    assert next(a for a in result.attempts if a.provider_slug == bad_slug).reason == (
        "ingestion_validation_failed")
    assert {r.external_id for r in await rows(session)} == {"event", "conflict"}


async def test_sql_error_propagates_and_caller_can_rollback(session):
    runner = await setup(session)
    original = runner.ingestion_repository.record_observation
    async def broken(**kwargs):
        await original(**kwargs)
        await session.execute(text("SELECT 1 / 0"))
    runner.ingestion_repository.record_observation = broken
    before = await snapshot(session, [SportsDataSource])
    with pytest.raises(DBAPIError):
        await runner.run(targets={"one": "player", "two": "player"})
    assert await rows(session) == []
    runner.registry.get("two").fetch_transfers.assert_not_awaited()
    assert before == await snapshot(session, [SportsDataSource])


async def test_outer_transaction_and_only_explicit_targets(session):
    runner = await setup(session)
    await session.commit()
    session.commit = AsyncMock(side_effect=AssertionError("No runner commit"))
    result = await runner.run(targets={"two": "player"})
    assert result.successes == 1
    runner.registry.get("one").check_health.assert_not_awaited()
    session.commit.assert_not_awaited()
    await session.rollback()
    assert await rows(session) == []


async def test_all_failures_are_dedicated_and_safe(session):
    runner = await setup(session)
    for provider in runner.registry.all():
        provider.fetch_transfers.side_effect = ValueError("secret https://private body")
    with pytest.raises(TransfersAllProvidersFailed) as caught:
        await runner.run(targets={"one": "player", "two": "player"})
    assert len(caught.value.attempts) == 2
    assert all(a.reason == "fetch_or_payload_failed" for a in caught.value.attempts)
    assert "secret" not in str(caught.value)
    assert await rows(session) == []


@pytest.mark.parametrize("targets", [{}, {"ONE": "player"}, {"one": " "}, {"one": "x"*161}])
async def test_invalid_targets_fail_before_provider_calls(session, targets):
    runner = await setup(session)
    with pytest.raises(ValueError):
        await runner.run(targets=targets)
    for provider in runner.registry.all():
        provider.check_health.assert_not_awaited()


@pytest.mark.parametrize("phase", ["health", "fetch"])
async def test_sql_errors_are_never_classified_as_provider_failures(session, phase):
    runner = await setup(session)
    provider = runner.registry.get("one")
    operation = provider.check_health if phase == "health" else provider.fetch_transfers
    operation.side_effect = DBAPIError("test", {}, Exception("database failure"))
    with pytest.raises(DBAPIError):
        await runner.run(targets={"one": "player", "two": "player"})
    runner.registry.get("two").check_health.assert_not_awaited()
    assert await rows(session) == []
