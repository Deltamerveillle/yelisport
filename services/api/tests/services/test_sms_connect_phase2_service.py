"""Tests for SMS Connect phase 2 review and delivery workflow."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.schemas.sms_connect import (
    SMSConnectTransitionRequest,
)
from app.services.sms_connect_service import (
    SMSConnectService,
)


ADMIN_ID = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)
ATHLETE_USER_ID = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)
INTEREST_ID = uuid.UUID(
    "33333333-3333-3333-3333-333333333333"
)


class FakeSession:
    pass


def make_service():
    service = SMSConnectService(
        FakeSession()
    )

    service.roles = SimpleNamespace(
        get_verified_admin_role=AsyncMock()
    )

    service.interests = SimpleNamespace(
        get_by_id=AsyncMock(),
        get_by_id_for_update=AsyncMock(),
        save=AsyncMock(),
        list_for_admin=AsyncMock(),
        list_for_athlete_user=AsyncMock(),
    )

    service.events = SimpleNamespace(
        create=AsyncMock(),
        list_for_interest=AsyncMock(),
    )

    return service


def make_interest(
    status="submitted",
):
    return SimpleNamespace(
        id=INTEREST_ID,
        status=status,
        reviewed_at=None,
        delivered_at=None,
    )


@pytest.mark.asyncio
async def test_admin_role_is_required():
    service = make_service()

    service.roles.get_verified_admin_role.return_value = None

    with pytest.raises(ForbiddenError):
        await service.list_admin_interests(
            admin_user_id=ADMIN_ID,
        )


@pytest.mark.asyncio
async def test_verified_admin_can_list_review_queue():
    service = make_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(role="admin")
    )

    expected = [
        make_interest()
    ]

    service.interests.list_for_admin.return_value = expected

    result = await service.list_admin_interests(
        admin_user_id=ADMIN_ID,
        interest_status="submitted",
        limit=20,
        offset=5,
    )

    assert result == expected

    service.interests.list_for_admin.assert_awaited_once_with(
        interest_status="submitted",
        limit=20,
        offset=5,
    )


@pytest.mark.asyncio
async def test_submitted_can_move_to_under_review():
    service = make_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(role="admin")
    )

    interest = make_interest(
        "submitted"
    )

    service.interests.get_by_id_for_update.return_value = (
        interest
    )
    service.interests.save.return_value = interest

    result = await service.transition_interest(
        interest_id=INTEREST_ID,
        admin_user_id=ADMIN_ID,
        data=SMSConnectTransitionRequest(
            status="under_review",
            note="Identity check started",
        ),
    )

    assert result.status == "under_review"

    event = service.events.create.await_args.args[0]

    assert event.interest_id == INTEREST_ID
    assert event.actor_user_id == ADMIN_ID
    assert event.actor_role == "admin"
    assert event.from_status == "submitted"
    assert event.to_status == "under_review"
    assert event.note == "Identity check started"


@pytest.mark.asyncio
async def test_submitted_cannot_skip_directly_to_approved():
    service = make_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(role="admin")
    )

    interest = make_interest(
        "submitted"
    )

    service.interests.get_by_id_for_update.return_value = (
        interest
    )

    with pytest.raises(ConflictError):
        await service.transition_interest(
            interest_id=INTEREST_ID,
            admin_user_id=ADMIN_ID,
            data=SMSConnectTransitionRequest(
                status="approved",
            ),
        )

    service.events.create.assert_not_awaited()
    service.interests.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_under_review_can_be_approved_and_sets_reviewed_at():
    service = make_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(role="admin")
    )

    interest = make_interest(
        "under_review"
    )

    service.interests.get_by_id_for_update.return_value = (
        interest
    )
    service.interests.save.return_value = interest

    result = await service.transition_interest(
        interest_id=INTEREST_ID,
        admin_user_id=ADMIN_ID,
        data=SMSConnectTransitionRequest(
            status="approved",
        ),
    )

    assert result.status == "approved"
    assert result.reviewed_at is not None
    assert result.delivered_at is None


@pytest.mark.asyncio
async def test_under_review_can_be_rejected_and_sets_reviewed_at():
    service = make_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(role="admin")
    )

    interest = make_interest(
        "under_review"
    )

    service.interests.get_by_id_for_update.return_value = (
        interest
    )
    service.interests.save.return_value = interest

    result = await service.transition_interest(
        interest_id=INTEREST_ID,
        admin_user_id=ADMIN_ID,
        data=SMSConnectTransitionRequest(
            status="rejected",
            note="Organization could not be verified",
        ),
    )

    assert result.status == "rejected"
    assert result.reviewed_at is not None


@pytest.mark.asyncio
async def test_approved_can_be_delivered_and_sets_delivered_at():
    service = make_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(role="admin")
    )

    athlete_id = uuid.uuid4()
    athlete_user_id = uuid.uuid4()

    interest = make_interest(
        "approved"
    )
    interest.athlete_id = athlete_id
    interest.organization_name = "Africa Talent FC"

    service.interests.get_by_id_for_update.return_value = (
        interest
    )
    service.interests.save.return_value = interest

    service.athletes = AsyncMock()
    service.notification_service = AsyncMock()

    service.athletes.get_by_id.return_value = (
        SimpleNamespace(
            id=athlete_id,
            user_id=athlete_user_id,
        )
    )

    result = await service.transition_interest(
        interest_id=INTEREST_ID,
        admin_user_id=ADMIN_ID,
        data=SMSConnectTransitionRequest(
            status="delivered",
        ),
    )

    assert result.status == "delivered"
    assert result.delivered_at is not None

    service.athletes.get_by_id.assert_awaited_once_with(
        athlete_id
    )

    (
        service.notification_service
        .create_sms_connect_delivery
        .assert_awaited_once_with(
            recipient_user_id=athlete_user_id,
            interest_id=INTEREST_ID,
            organization_name=(
                interest.organization_name
            ),
        )
    )

@pytest.mark.asyncio
async def test_delivered_can_be_closed():
    service = make_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(role="admin")
    )

    interest = make_interest(
        "delivered"
    )

    service.interests.get_by_id_for_update.return_value = (
        interest
    )
    service.interests.save.return_value = interest

    result = await service.transition_interest(
        interest_id=INTEREST_ID,
        admin_user_id=ADMIN_ID,
        data=SMSConnectTransitionRequest(
            status="closed",
        ),
    )

    assert result.status == "closed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_status,target_status",
    [
        ("submitted", "delivered"),
        ("submitted", "closed"),
        ("approved", "closed"),
        ("rejected", "under_review"),
        ("rejected", "approved"),
        ("closed", "under_review"),
    ],
)
async def test_invalid_transitions_are_blocked(
    current_status,
    target_status,
):
    service = make_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(role="admin")
    )

    interest = make_interest(
        current_status
    )

    service.interests.get_by_id_for_update.return_value = (
        interest
    )

    with pytest.raises(ConflictError):
        await service.transition_interest(
            interest_id=INTEREST_ID,
            admin_user_id=ADMIN_ID,
            data=SMSConnectTransitionRequest(
                status=target_status,
            ),
        )


@pytest.mark.asyncio
async def test_missing_interest_returns_not_found():
    service = make_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(role="admin")
    )

    service.interests.get_by_id_for_update.return_value = None

    with pytest.raises(NotFoundError):
        await service.transition_interest(
            interest_id=INTEREST_ID,
            admin_user_id=ADMIN_ID,
            data=SMSConnectTransitionRequest(
                status="under_review",
            ),
        )


@pytest.mark.asyncio
async def test_athlete_inbox_is_scoped_to_authenticated_athlete():
    service = make_service()

    expected = [
        make_interest("delivered")
    ]

    service.interests.list_for_athlete_user.return_value = expected

    result = await service.list_athlete_inbox(
        ATHLETE_USER_ID
    )

    assert result == expected

    service.interests.list_for_athlete_user.assert_awaited_once_with(
        ATHLETE_USER_ID
    )


@pytest.mark.asyncio
async def test_admin_can_read_interest_audit_history():
    service = make_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(role="admin")
    )

    interest = make_interest(
        "approved"
    )

    service.interests.get_by_id.return_value = interest

    expected = [
        SimpleNamespace(
            from_status="submitted",
            to_status="under_review",
        ),
        SimpleNamespace(
            from_status="under_review",
            to_status="approved",
        ),
    ]

    service.events.list_for_interest.return_value = expected

    result = await service.list_interest_events(
        interest_id=INTEREST_ID,
        admin_user_id=ADMIN_ID,
    )

    assert result == expected

    service.events.list_for_interest.assert_awaited_once_with(
        INTEREST_ID
    )
