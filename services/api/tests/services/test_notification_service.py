"""Tests for SMS notification business rules."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError
from app.services.notification_service import NotificationService


USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()
INTEREST_ID = uuid.uuid4()
NOTIFICATION_ID = uuid.uuid4()


def build_service() -> NotificationService:
    service = NotificationService(
        SimpleNamespace()
    )
    service.notifications = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_create_sms_connect_delivery_creates_notification():
    service = build_service()

    service.notifications.get_by_dedupe_key.return_value = None

    async def fake_create(notification):
        notification.id = NOTIFICATION_ID
        notification.created_at = datetime.now(
            timezone.utc
        )
        return notification

    service.notifications.create.side_effect = fake_create

    result = await service.create_sms_connect_delivery(
        recipient_user_id=USER_ID,
        interest_id=INTEREST_ID,
        organization_name="Africa Talent FC",
    )

    assert result.recipient_user_id == USER_ID
    assert (
        result.notification_type
        == "sms_connect_interest_delivered"
    )
    assert result.resource_type == "sms_connect_interest"
    assert result.resource_id == INTEREST_ID
    assert result.is_read is False
    assert result.dedupe_key == (
        f"sms_connect:{INTEREST_ID}:delivered"
    )
    assert "Africa Talent FC" in result.body
    assert "vérifié" not in result.body

    service.notifications.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_sms_connect_delivery_is_idempotent():
    service = build_service()

    existing = SimpleNamespace(
        id=NOTIFICATION_ID,
        dedupe_key=(
            f"sms_connect:{INTEREST_ID}:delivered"
        ),
    )

    service.notifications.get_by_dedupe_key.return_value = existing

    result = await service.create_sms_connect_delivery(
        recipient_user_id=USER_ID,
        interest_id=INTEREST_ID,
        organization_name="Africa Talent FC",
    )

    assert result is existing
    service.notifications.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_my_notifications_is_scoped_to_user():
    service = build_service()

    expected = [
        SimpleNamespace(id=NOTIFICATION_ID)
    ]

    service.notifications.list_for_recipient.return_value = expected

    result = await service.list_my_notifications(
        USER_ID,
        unread_only=True,
        limit=20,
        offset=5,
    )

    assert result == expected

    service.notifications.list_for_recipient.assert_awaited_once_with(
        USER_ID,
        unread_only=True,
        limit=20,
        offset=5,
    )


@pytest.mark.asyncio
async def test_unread_count_is_scoped_to_user():
    service = build_service()

    service.notifications.count_unread.return_value = 4

    result = await service.unread_count(
        USER_ID
    )

    assert result == 4

    service.notifications.count_unread.assert_awaited_once_with(
        USER_ID
    )


@pytest.mark.asyncio
async def test_mark_read_marks_notification_once():
    service = build_service()

    notification = SimpleNamespace(
        id=NOTIFICATION_ID,
        recipient_user_id=USER_ID,
        is_read=False,
        read_at=None,
    )

    service.notifications.get_for_recipient_for_update.return_value = (
        notification
    )

    async def fake_save(value):
        return value

    service.notifications.save.side_effect = fake_save

    result = await service.mark_read(
        notification_id=NOTIFICATION_ID,
        user_id=USER_ID,
    )

    assert result.is_read is True
    assert result.read_at is not None
    assert result.read_at.tzinfo is not None

    service.notifications.get_for_recipient_for_update.assert_awaited_once_with(
        notification_id=NOTIFICATION_ID,
        recipient_user_id=USER_ID,
    )


@pytest.mark.asyncio
async def test_mark_read_is_idempotent():
    service = build_service()

    original_time = datetime(
        2026,
        9,
        5,
        0,
        0,
        tzinfo=timezone.utc,
    )

    notification = SimpleNamespace(
        id=NOTIFICATION_ID,
        recipient_user_id=USER_ID,
        is_read=True,
        read_at=original_time,
    )

    service.notifications.get_for_recipient_for_update.return_value = (
        notification
    )

    async def fake_save(value):
        return value

    service.notifications.save.side_effect = fake_save

    result = await service.mark_read(
        notification_id=NOTIFICATION_ID,
        user_id=USER_ID,
    )

    assert result.is_read is True
    assert result.read_at == original_time


@pytest.mark.asyncio
async def test_mark_read_cannot_access_another_users_notification():
    service = build_service()

    service.notifications.get_for_recipient_for_update.return_value = None

    with pytest.raises(
        NotFoundError,
        match="Notification not found",
    ):
        await service.mark_read(
            notification_id=NOTIFICATION_ID,
            user_id=OTHER_USER_ID,
        )

    service.notifications.save.assert_not_awaited()
