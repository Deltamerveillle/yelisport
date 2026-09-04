"""Persistence for SMS Connect transition audit events."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sms_connect_interest_event import (
    SMSConnectInterestEvent,
)


class SMSConnectInterestEventRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def create(
        self,
        event: SMSConnectInterestEvent,
    ) -> SMSConnectInterestEvent:
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def list_for_interest(
        self,
        interest_id: uuid.UUID,
    ) -> Sequence[SMSConnectInterestEvent]:
        result = await self.session.scalars(
            select(SMSConnectInterestEvent)
            .where(
                SMSConnectInterestEvent.interest_id
                == interest_id
            )
            .order_by(
                SMSConnectInterestEvent.created_at.asc()
            )
        )
        return result.all()
