"""Opportunity persistence and explicitly projected, ownership-scoped reads."""

import uuid
from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.athlete import Athlete
from app.models.sms_connect_interest import SMSConnectInterest as Interest
from app.models.sms_connect_opportunity import SMSConnectOpportunity as Opportunity
from app.models.sms_connect_opportunity import SMSConnectOpportunityEvent


class SMSConnectOpportunityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, opportunity_id: uuid.UUID) -> Opportunity | None:
        return await self.session.get(Opportunity, opportunity_id)

    async def get_for_interest_for_update(self, interest_id: uuid.UUID) -> Opportunity | None:
        return cast(
            Opportunity | None,
            await self.session.scalar(
            select(Opportunity)
            .where(
                Opportunity.interest_id == interest_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
            ),
        )

    async def create(self, opportunity: Opportunity) -> Opportunity:
        self.session.add(opportunity)
        await self.session.flush()
        return opportunity

    async def add_event(self, event: SMSConnectOpportunityEvent) -> None:
        self.session.add(event)
        await self.session.flush()

    @staticmethod
    def _read_query() -> Select[Any]:
        # Neither user IDs nor personal contact fields are loaded into the response.
        return select(
            Opportunity.id,
            Opportunity.interest_id,
            Opportunity.status,
            Opportunity.opened_at,
            Opportunity.closed_at,
            Opportunity.created_at,
            Opportunity.updated_at,
            Interest.organization_name,
            Interest.requester_role,
            Interest.interest_type,
            Interest.subject,
            Interest.message,
        ).join(Interest, Interest.id == Opportunity.interest_id)

    async def get_response(self, opportunity_id: uuid.UUID) -> RowMapping:
        result = await self.session.execute(
            self._read_query().where(Opportunity.id == opportunity_id)
        )
        return result.mappings().one()

    async def list_for_athlete(self, user_id: uuid.UUID) -> Sequence[RowMapping]:
        result = await self.session.execute(
            self._read_query()
            .join(
                Athlete,
                Athlete.id == Interest.athlete_id,
            )
            .where(Athlete.user_id == user_id)
            .order_by(Opportunity.opened_at.desc(), Opportunity.id)
        )
        return result.mappings().all()

    async def list_for_requester(self, user_id: uuid.UUID) -> Sequence[RowMapping]:
        result = await self.session.execute(
            self._read_query()
            .where(
                Interest.requester_user_id == user_id,
            )
            .order_by(Opportunity.opened_at.desc(), Opportunity.id)
        )
        return result.mappings().all()
