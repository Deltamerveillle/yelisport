"""Persistence for SMS notification projections."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


class NotificationRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def create(
        self,
        notification: Notification,
    ) -> Notification:
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(
            notification
        )
        return notification

    async def get_by_dedupe_key(
        self,
        dedupe_key: str,
    ) -> Notification | None:
        return await self.session.scalar(
            select(Notification).where(
                Notification.dedupe_key
                == dedupe_key
            )
        )

    async def list_for_recipient(
        self,
        recipient_user_id: uuid.UUID,
        *,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Notification]:
        stmt = select(Notification).where(
            Notification.recipient_user_id
            == recipient_user_id
        )

        if unread_only:
            stmt = stmt.where(
                Notification.is_read.is_(
                    False
                )
            )

        stmt = (
            stmt
            .order_by(
                Notification.created_at.desc(),
                Notification.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.scalars(
            stmt
        )
        return result.all()

    async def count_unread(
        self,
        recipient_user_id: uuid.UUID,
    ) -> int:
        count = await self.session.scalar(
            select(func.count(Notification.id))
            .where(
                Notification.recipient_user_id
                == recipient_user_id,
                Notification.is_read.is_(
                    False
                ),
            )
        )

        return int(count or 0)

    async def get_for_recipient_for_update(
        self,
        *,
        notification_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
    ) -> Notification | None:
        return await self.session.scalar(
            select(Notification)
            .where(
                Notification.id
                == notification_id,
                Notification.recipient_user_id
                == recipient_user_id,
            )
            .with_for_update()
        )

    async def save(
        self,
        notification: Notification,
    ) -> Notification:
        await self.session.flush()
        await self.session.refresh(
            notification
        )
        return notification
