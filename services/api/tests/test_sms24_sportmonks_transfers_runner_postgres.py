"""Real Sportmonks adapter + unchanged TransfersRunner, mocked HTTP and isolated DB."""

import httpx
import pytest
from sqlalchemy import select

from app.models.athlete import Athlete
from app.models.sports_live import SportsDataSource, SportsDataSourceCapability
from app.models.sports_transfers import (
    SportsAthleteIdentityLink,
    SportsCanonicalTransfer,
    SportsTransferObservation,
)
from app.models.user import User
from app.sms24.providers.registry import ProviderRegistry
from app.sms24.providers.sportmonks import SportmonksProvider
from app.sms24.transfers_runner import TransfersAllProvidersFailed, TransfersRunner
from tests import test_sms24_transfers_postgres as foundation
from tests.test_sms24_sportmonks_transfers import PLAYER, TOKEN, envelope, transfer
from tests.test_sms24_transfers_postgres import NOW, add, count

connection = foundation.connection
session = foundation.session


@pytest.mark.parametrize("active", [False, True])
async def test_adapter_runner_persistence_and_explicit_capability(session, active):
    source = await add(
        session,
        SportsDataSource,
        slug="sportmonks",
        name="Sportmonks",
        health_status="degraded",
        last_success_at=NOW,
        last_failure_at=NOW,
        last_checked_at=NOW,
    )
    if active:
        await add(
            session,
            SportsDataSourceCapability,
            source_id=source.id,
            capability="transfers",
            is_active=True,
        )
    before = (await session.execute(select(SportsDataSource.__table__))).mappings().all()
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.startswith("/v3/football/fixtures/date/"):
            return httpx.Response(200, json={"data": []})
        assert request.url.path == f"/v3/football/transfers/players/{PLAYER}"
        return httpx.Response(200, json=envelope([transfer()]))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        registry = ProviderRegistry()
        registry.register(SportmonksProvider(api_key=TOKEN, client=client))
        runner = TransfersRunner(session=session, registry=registry)
        if not active:
            with pytest.raises(TransfersAllProvidersFailed):
                await runner.run(targets={"sportmonks": PLAYER})
            assert calls == []
            assert await count(session, SportsTransferObservation) == 0
        else:
            for _ in range(2):
                result = await runner.run(targets={"sportmonks": PLAYER})
                assert result.successes == result.observations_processed == 1
            assert len(calls) == 4
            observation = (await session.scalars(select(SportsTransferObservation))).one()
            assert observation.external_id == "112"
            assert observation.athlete_external_id == PLAYER
            assert observation.metadata_json == transfer()
            assert observation.metadata_json["amount"] is None
            assert observation.reported_type == "219"
            assert observation.canonical_transfer_id is observation.athlete_competitor_id is None
    assert before == (await session.execute(select(SportsDataSource.__table__))).mappings().all()
    for model in (User, Athlete, SportsCanonicalTransfer, SportsAthleteIdentityLink):
        assert await count(session, model) == 0
