"""Security and decision tests for SMS Proof."""

import uuid
from types import SimpleNamespace

import pytest

from app.core.exceptions import ForbiddenError
from app.models.athlete_performance_verification import (
    AthletePerformanceVerification,
)
from app.services.sms_proof_service import SMSProofService


PERFORMANCE_ID = uuid.uuid4()
ATHLETE_ID = uuid.uuid4()
VERIFIER_ID = uuid.uuid4()
OWNER_ID = uuid.uuid4()


class FakeSession:
    def __init__(self, performance=None):
        self.performance = performance
        self.added = []
        self.flushed = False

    async def scalar(self, statement):
        return self.performance

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushed = True


def make_service(*, owner_id=OWNER_ID, authorized=True):
    performance = SimpleNamespace(
        id=PERFORMANCE_ID,
        athlete_id=ATHLETE_ID,
        verification_status="declared",
    )
    session = FakeSession(performance)
    service = SMSProofService(session)

    async def fake_admin(*, user_id):
        assert user_id == VERIFIER_ID
        return SimpleNamespace(role="admin") if authorized else None

    async def fake_athlete(athlete_id):
        assert athlete_id == ATHLETE_ID
        return SimpleNamespace(
            id=ATHLETE_ID,
            user_id=owner_id,
        )

    service.roles.get_verified_admin_role = fake_admin
    service.athletes.get_by_id = fake_athlete

    return service, session, performance


@pytest.mark.asyncio
async def test_unverified_user_cannot_verify():
    service, session, performance = make_service(
        authorized=False
    )

    with pytest.raises(ForbiddenError):
        await service.verify_performance(
            performance_id=PERFORMANCE_ID,
            verifier_user_id=VERIFIER_ID,
            decision="verified",
            reason="Official result checked",
        )

    assert performance.verification_status == "declared"
    assert session.added == []


@pytest.mark.asyncio
async def test_athlete_cannot_verify_own_performance():
    service, session, performance = make_service(
        owner_id=VERIFIER_ID
    )

    with pytest.raises(ForbiddenError):
        await service.verify_performance(
            performance_id=PERFORMANCE_ID,
            verifier_user_id=VERIFIER_ID,
            decision="verified",
            reason="Self approval",
        )

    assert performance.verification_status == "declared"
    assert session.added == []


@pytest.mark.asyncio
async def test_empty_reason_is_rejected():
    service, session, performance = make_service()

    with pytest.raises(ValueError):
        await service.verify_performance(
            performance_id=PERFORMANCE_ID,
            verifier_user_id=VERIFIER_ID,
            decision="verified",
            reason="   ",
        )

    assert performance.verification_status == "declared"
    assert session.added == []


@pytest.mark.asyncio
async def test_valid_decision_creates_audit_record():
    service, session, performance = make_service()

    result = await service.verify_performance(
        performance_id=PERFORMANCE_ID,
        verifier_user_id=VERIFIER_ID,
        decision="documented",
        reason="  Federation document reviewed  ",
        evidence={"source": "federation"},
    )

    assert isinstance(result, AthletePerformanceVerification)
    assert result.performance_id == PERFORMANCE_ID
    assert result.verifier_user_id == VERIFIER_ID
    assert result.decision == "documented"
    assert result.reason == "Federation document reviewed"
    assert result.evidence == {"source": "federation"}
    assert performance.verification_status == "documented"
    assert session.added == [result]
    assert session.flushed is True
