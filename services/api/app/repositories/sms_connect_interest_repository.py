"""Persistence for SMS Connect interest requests."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
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

    async def get_by_id_for_update(
        self,
        interest_id: uuid.UUID,
    ) -> SMSConnectInterest | None:
        return await self.session.scalar(
            select(SMSConnectInterest)
            .where(
                SMSConnectInterest.id
                == interest_id
            )
            .with_for_update()
        )

    async def save(
        self,
        interest: SMSConnectInterest,
    ) -> SMSConnectInterest:
        await self.session.flush()
        await self.session.refresh(interest)
        return interest

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

    async def list_for_admin(
        self,
        *,
        interest_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[SMSConnectInterest]:
        query = select(SMSConnectInterest)

        if interest_status is not None:
            query = query.where(
                SMSConnectInterest.status
                == interest_status
            )

        result = await self.session.scalars(
            query
            .order_by(
                SMSConnectInterest.created_at.asc()
            )
            .limit(min(max(limit, 1), 100))
            .offset(max(offset, 0))
        )

        return result.all()

    async def list_for_athlete_user(
        self,
        athlete_user_id: uuid.UUID,
    ) -> Sequence[SMSConnectInterest]:
        result = await self.session.scalars(
            select(SMSConnectInterest)
            .join(
                Athlete,
                Athlete.id
                == SMSConnectInterest.athlete_id,
            )
            .where(
                Athlete.user_id == athlete_user_id,
                SMSConnectInterest.status.in_(
                    (
                        "delivered",
                        "closed",
                    )
                ),
            )
            .order_by(
                SMSConnectInterest.delivered_at.desc()
            )
        )

        return result.all()
