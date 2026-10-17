"""Tests for the SMS Proof verification API endpoint."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints.sms_proof import verify_athlete_performance
from app.schemas.sms_proof import SMSProofDecisionRequest


PERFORMANCE_ID = uuid.uuid4()
ADMIN_ID = uuid.uuid4()


@pytest.mark.asyncio
async def test_sms_proof_endpoint_commits(monkeypatch):
    session = SimpleNamespace(
        commit=AsyncMock(),
        refresh=AsyncMock(),
        rollback=AsyncMock(),
    )

    verification = SimpleNamespace(
        id=uuid.uuid4(),
        performance_id=PERFORMANCE_ID,
        verifier_user_id=ADMIN_ID,
        decision="verified",
        reason="Official result checked",
        evidence={},
        created_at=datetime.now(timezone.utc),
    )

    service = SimpleNamespace(
        verify_performance=AsyncMock(return_value=verification)
    )

    monkeypatch.setattr(
        "app.api.v1.endpoints.sms_proof.SMSProofService",
        lambda session: service,
    )

    result = await verify_athlete_performance(
        performance_id=PERFORMANCE_ID,
        data=SMSProofDecisionRequest(
            decision="verified",
            reason="Official result checked",
        ),
        current_user=SimpleNamespace(id=ADMIN_ID),
        session=session,
    )

    assert result is verification
    service.verify_performance.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(verification)
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_sms_proof_endpoint_rolls_back_on_failure(monkeypatch):
    session = SimpleNamespace(
        commit=AsyncMock(),
        refresh=AsyncMock(),
        rollback=AsyncMock(),
    )

    service = SimpleNamespace(
        verify_performance=AsyncMock(
            side_effect=RuntimeError("Verification failed")
        )
    )

    monkeypatch.setattr(
        "app.api.v1.endpoints.sms_proof.SMSProofService",
        lambda session: service,
    )

    with pytest.raises(RuntimeError, match="Verification failed"):
        await verify_athlete_performance(
            performance_id=PERFORMANCE_ID,
            data=SMSProofDecisionRequest(
                decision="verified",
                reason="Official result checked",
            ),
            current_user=SimpleNamespace(id=ADMIN_ID),
            session=session,
        )

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
