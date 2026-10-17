"""Security tests for SMS Proof verification history."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.services.sms_proof_service import SMSProofService


PERFORMANCE_ID = uuid.uuid4()
ADMIN_ID = uuid.uuid4()


def make_service(role, performance=None, records=None):
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=performance),
        scalars=AsyncMock(
            return_value=SimpleNamespace(
                all=lambda: records if records is not None else []
            )
        ),
    )

    service = SMSProofService.__new__(SMSProofService)
    service.session = session
    service.roles = SimpleNamespace(
        get_verified_admin_role=AsyncMock(return_value=role)
    )

    return service, session


@pytest.mark.asyncio
async def test_history_rejects_unauthorized_user():
    service, session = make_service(role=None)

    with pytest.raises(ForbiddenError):
        await service.list_verifications(
            performance_id=PERFORMANCE_ID,
            requester_user_id=ADMIN_ID,
        )

    session.scalar.assert_not_awaited()
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_history_rejects_missing_performance():
    service, session = make_service(
        role=SimpleNamespace(role="admin"),
        performance=None,
    )

    with pytest.raises(NotFoundError):
        await service.list_verifications(
            performance_id=PERFORMANCE_ID,
            requester_user_id=ADMIN_ID,
        )

    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_history_returns_records_to_admin():
    records = [
        SimpleNamespace(id=uuid.uuid4()),
        SimpleNamespace(id=uuid.uuid4()),
    ]

    service, session = make_service(
        role=SimpleNamespace(role="admin"),
        performance=SimpleNamespace(id=PERFORMANCE_ID),
        records=records,
    )

    result = await service.list_verifications(
        performance_id=PERFORMANCE_ID,
        requester_user_id=ADMIN_ID,
    )

    assert result == records
    service.roles.get_verified_admin_role.assert_awaited_once_with(
        user_id=ADMIN_ID
    )
    session.scalars.assert_awaited_once()
