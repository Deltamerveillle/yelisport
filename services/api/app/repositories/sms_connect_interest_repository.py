"""Persistence for SMS Connect interest requests."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sms_connect_interest import (
    SMSConnectInterest,
)


class SMSConnectInterestRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def create(
        self,
        interest: SMSConnectInterest,
    ) -> SMSConnectInterest:
        self.session.add(interest)
        await self.session.flush()
        await self.session.refresh(interest)
        return interest

    async def get_by_id(
        self,
        interest_id: uuid.UUID,
    ) -> SMSConnectInterest | None:
        return await self.session.scalar(
            select(SMSConnectInterest).where(
                SMSConnectInterest.id
                == interest_id
            )
        )

    async def list_for_requester(
        self,
        requester_user_id: uuid.UUID,
    ) -> Sequence[SMSConnectInterest]:
        result = await self.session.scalars(
            select(SMSConnectInterest)
            .where(
                SMSConnectInterest.requester_user_id
                == requester_user_id
            )
            .order_by(
                SMSConnectInterest.created_at.desc()
            )
        )

        return result.all()
