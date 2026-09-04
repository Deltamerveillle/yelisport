"""Tests for SMS Connect business rules."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.schemas.sms_connect import SMSConnectInterestCreate
from app.services.sms_connect_service import SMSConnectService


ATHLETE_ID = uuid.uuid4()
ATHLETE_OWNER_ID = uuid.uuid4()
REQUESTER_ID = uuid.uuid4()


def build_service() -> SMSConnectService:
    service = SMSConnectService(
        SimpleNamespace()
    )

    service.athletes = AsyncMock()
    service.roles = AsyncMock()
    service.interests = AsyncMock()

    return service


def make_data() -> SMSConnectInterestCreate:
    return SMSConnectInterestCreate(
        interest_type="trial",
        organization_name="SMS Football Club",
        subject="Invitation à un essai",
        message=(
            "Nous souhaitons inviter cet athlète "
            "à un essai professionnel."
        ),
    )


@pytest.mark.asyncio
async def test_verified_professional_can_create_interest():
    service = build_service()

    service.athletes.get_by_id.return_value = SimpleNamespace(
        id=ATHLETE_ID,
        user_id=ATHLETE_OWNER_ID,
    )

    service.roles.get_verified_professional_role.return_value = (
        SimpleNamespace(
            role="club",
            is_active=True,
            is_verified=True,
        )
    )

    async def fake_create(interest):
        return interest

    service.interests.create.side_effect = fake_create

    result = await service.create_interest(
        athlete_id=ATHLETE_ID,
        requester_user_id=REQUESTER_ID,
        data=make_data(),
    )

    assert result.athlete_id == ATHLETE_ID
    assert result.requester_user_id == REQUESTER_ID
    assert result.requester_role == "club"
    assert result.interest_type == "trial"
    assert result.status == "submitted"

    (
        service.roles
        .get_verified_professional_role
        .assert_awaited_once_with(
            user_id=REQUESTER_ID
        )
    )


@pytest.mark.asyncio
async def test_unverified_professional_cannot_create_interest():
    service = build_service()

    service.athletes.get_by_id.return_value = SimpleNamespace(
        id=ATHLETE_ID,
        user_id=ATHLETE_OWNER_ID,
    )

    service.roles.get_verified_professional_role.return_value = None

    with pytest.raises(
        ForbiddenError,
        match="verified club",
    ):
        await service.create_interest(
            athlete_id=ATHLETE_ID,
            requester_user_id=REQUESTER_ID,
            data=make_data(),
        )

    service.interests.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_athlete_cannot_contact_self():
    service = build_service()

    service.athletes.get_by_id.return_value = SimpleNamespace(
        id=ATHLETE_ID,
        user_id=REQUESTER_ID,
    )

    with pytest.raises(
        ForbiddenError,
        match="cannot submit professional interest",
    ):
        await service.create_interest(
            athlete_id=ATHLETE_ID,
            requester_user_id=REQUESTER_ID,
            data=make_data(),
        )

    (
        service.roles
        .get_verified_professional_role
        .assert_not_awaited()
    )

    service.interests.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_athlete_returns_not_found():
    service = build_service()

    service.athletes.get_by_id.return_value = None

    with pytest.raises(
        NotFoundError,
        match="Athlete not found",
    ):
        await service.create_interest(
            athlete_id=ATHLETE_ID,
            requester_user_id=REQUESTER_ID,
            data=make_data(),
        )

    service.interests.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_my_interests_is_scoped_to_requester():
    service = build_service()

    expected = [
        SimpleNamespace(
            id=uuid.uuid4()
        )
    ]

    service.interests.list_for_requester.return_value = expected

    result = await service.list_my_interests(
        REQUESTER_ID
    )

    assert result == expected

    (
        service.interests
        .list_for_requester
        .assert_awaited_once_with(
            REQUESTER_ID
        )
    )
