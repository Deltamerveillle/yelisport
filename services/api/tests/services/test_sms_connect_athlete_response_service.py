"""Ownership, delivery gating and independent athlete response audit."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.schemas.sms_connect import SMSConnectAthleteResponseRequest
from app.services.sms_connect_service import SMSConnectService


def setup(status="delivered"):
    owner = uuid.uuid4()
    interest = SimpleNamespace(
        id=uuid.uuid4(),
        athlete_id=uuid.uuid4(),
        status=status,
        athlete_response="pending",
        athlete_responded_at=None,
    )
    service = SMSConnectService(AsyncMock())
    service.interests = AsyncMock()
    service.interests.get_by_id_for_update.return_value = interest
    service.interests.save.return_value = interest
    service.athletes = AsyncMock()
    service.athletes.get_by_id.return_value = SimpleNamespace(user_id=owner)
    service.opportunities = AsyncMock()
    service.opportunities.get_for_interest_for_update.return_value = None
    service.opportunities.create.side_effect = lambda opportunity: opportunity
    service.events = AsyncMock()
    service.notification_service = AsyncMock()
    return service, interest, owner


@pytest.mark.parametrize("decision", ["interested", "declined"])
async def test_owner_decides_without_admin_transition_or_contact(decision):
    service, interest, owner = setup()
    result = await service.respond_to_interest(
        interest_id=interest.id,
        athlete_user_id=owner,
        data=SMSConnectAthleteResponseRequest(athlete_response=decision),
    )
    assert result.status == "delivered" and result.athlete_response == decision
    assert result.athlete_responded_at.utcoffset().total_seconds() == 0
    event = service.interests.add_athlete_response_event.await_args.args[0]
    assert event.interest_id == interest.id and event.actor_user_id == owner
    assert event.from_response == "pending" and event.to_response == decision
    assert event.created_at == interest.athlete_responded_at
    service.events.create.assert_not_awaited()
    assert not service.notification_service.mock_calls


@pytest.mark.parametrize("status", ["submitted", "under_review", "approved", "rejected", "closed"])
async def test_not_delivered_cannot_be_answered(status):
    service, interest, owner = setup(status)
    with pytest.raises(ConflictError):
        await service.respond_to_interest(
            interest_id=interest.id,
            athlete_user_id=owner,
            data=SMSConnectAthleteResponseRequest(athlete_response="interested"),
        )
    service.interests.save.assert_not_awaited()
    service.interests.add_athlete_response_event.assert_not_awaited()
    assert interest.athlete_response == "pending"


@pytest.mark.parametrize("missing", ["interest", "athlete", "owner"])
async def test_missing_and_forbidden(missing):
    service, interest, owner = setup()
    if missing == "interest":
        service.interests.get_by_id_for_update.return_value = None
    if missing == "athlete":
        service.athletes.get_by_id.return_value = None
    with pytest.raises(ForbiddenError if missing == "owner" else NotFoundError):
        await service.respond_to_interest(
            interest_id=interest.id,
            athlete_user_id=uuid.uuid4() if missing == "owner" else owner,
            data=SMSConnectAthleteResponseRequest(athlete_response="declined"),
        )
    service.interests.save.assert_not_awaited()
    service.interests.add_athlete_response_event.assert_not_awaited()


async def test_retry_is_idempotent_and_change_is_audited():
    service, interest, owner = setup()

    async def respond(value):
        return await service.respond_to_interest(
            interest_id=interest.id,
            athlete_user_id=owner,
            data=SMSConnectAthleteResponseRequest(athlete_response=value),
        )

    await respond("interested")
    timestamp = interest.athlete_responded_at
    await respond("interested")
    assert interest.athlete_responded_at == timestamp
    assert service.interests.add_athlete_response_event.await_count == 1
    await respond("declined")
    assert service.interests.add_athlete_response_event.await_count == 2
    event = service.interests.add_athlete_response_event.await_args.args[0]
    assert (event.from_response, event.to_response) == ("interested", "declined")
