"""User notification projection service."""

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.notification import Notification
from app.repositories.notification_repository import (
    NotificationRepository,
)


class NotificationService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.notifications = (
            NotificationRepository(
                session
            )
        )

    async def create_sms_connect_delivery(
        self,
        *,
        recipient_user_id: uuid.UUID,
        interest_id: uuid.UUID,
        organization_name: str,
    ) -> Notification:
        """
        Create one idempotent notification when SMS
        formally delivers professional interest.
        """

        dedupe_key = (
            f"sms_connect:{interest_id}:delivered"
        )

        existing = (
            await self.notifications
            .get_by_dedupe_key(
                dedupe_key
            )
        )

        if existing is not None:
            return existing

        notification = Notification(
            recipient_user_id=recipient_user_id,
            notification_type=(
                "sms_connect_interest_delivered"
            ),
            title=(
                "Nouvel intérêt professionnel"
            ),
            body=(
                "SMS vous a transmis un nouvel "
                "intérêt professionnel de "
                f"{organization_name}."
            ),
            source="sms",
            resource_type=(
                "sms_connect_interest"
            ),
            resource_id=interest_id,
            dedupe_key=dedupe_key,
            is_read=False,
        )

        return await self.notifications.create(
            notification
        )

    async def list_my_notifications(
        self,
        user_id: uuid.UUID,
        *,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Notification]:
        return (
            await self.notifications
            .list_for_recipient(
                user_id,
                unread_only=unread_only,
                limit=limit,
                offset=offset,
            )
        )

    async def unread_count(
        self,
        user_id: uuid.UUID,
    ) -> int:
        return (
            await self.notifications
            .count_unread(
                user_id
            )
        )

    async def mark_read(
        self,
        *,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Notification:
        notification = (
            await self.notifications
            .get_for_recipient_for_update(
                notification_id=(
                    notification_id
                ),
                recipient_user_id=user_id,
            )
        )

        if notification is None:
            raise NotFoundError(
                "Notification not found"
            )

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(
                timezone.utc
            )

        return await self.notifications.save(
            notification
        )
