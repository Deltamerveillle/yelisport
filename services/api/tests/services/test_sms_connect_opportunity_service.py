"""Conservative opportunity transitions and authorization."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.schemas.sms_connect import SMSConnectOpportunityTransitionRequest
from app.services.sms_connect_service import SMSConnectService


@pytest.mark.parametrize(
    "previous,target,valid",
    [
        ("active", "progressing", True),
        ("active", "unsuccessful", True),
        ("progressing", "successful", True),
        ("progressing", "unsuccessful", True),
        ("active", "successful", False),
        ("withdrawn", "progressing", False),
        ("successful", "unsuccessful", False),
        ("unsuccessful", "progressing", False),
        ("progressing", "progressing", False),
    ],
)
async def test_admin_transitions(previous, target, valid):
    service = SMSConnectService(AsyncMock())
    service.roles = AsyncMock()
    service.roles.get_verified_admin_role.return_value = SimpleNamespace(role="admin")
    service.interests = AsyncMock()
    service.opportunities = AsyncMock()
    opportunity = SimpleNamespace(
        id=uuid.uuid4(), interest_id=uuid.uuid4(), status=previous, closed_at=None
    )
    service.opportunities.get_by_id.return_value = opportunity
    service.opportunities.get_for_interest_for_update.return_value = opportunity
    kwargs = dict(
        opportunity_id=opportunity.id,
        admin_user_id=uuid.uuid4(),
        data=SMSConnectOpportunityTransitionRequest(status=target),
    )
    if not valid:
        with pytest.raises(ConflictError):
            await service.transition_opportunity(**kwargs)
        service.opportunities.add_event.assert_not_awaited()
        assert opportunity.status == previous
    else:
        await service.transition_opportunity(**kwargs)
        service.interests.get_by_id_for_update.assert_awaited_once_with(opportunity.interest_id)
        assert opportunity.status == target
        event = service.opportunities.add_event.await_args.args[0]
        assert event.from_status == previous and event.to_status == target
        assert event.source == "sms_admin" and event.actor_user_id == kwargs["admin_user_id"]
        assert (opportunity.closed_at is not None) == (target != "progressing")


@pytest.mark.parametrize("missing", ["admin", "opportunity"])
async def test_admin_required_and_missing_opportunity(missing):
    service = SMSConnectService(AsyncMock())
    service.roles = AsyncMock()
    service.roles.get_verified_admin_role.return_value = (
        None if missing == "admin" else SimpleNamespace(role="admin")
    )
    service.opportunities = AsyncMock()
    service.opportunities.get_by_id.return_value = None
    with pytest.raises(ForbiddenError if missing == "admin" else NotFoundError):
        await service.transition_opportunity(
            opportunity_id=uuid.uuid4(),
            admin_user_id=uuid.uuid4(),
            data=SMSConnectOpportunityTransitionRequest(status="progressing"),
        )
    service.opportunities.add_event.assert_not_awaited()
