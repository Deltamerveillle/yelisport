"""Repository for SMS Talent applications."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.talent_application import TalentApplication


class TalentApplicationRepository:
    """Persistence operations for SMS Talent applications."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        application: TalentApplication,
    ) -> TalentApplication:
        self.session.add(application)
        await self.session.flush()
        await self.session.refresh(application)
        return application

    async def get_by_id(
        self,
        application_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> TalentApplication | None:
        query = select(TalentApplication).where(
            TalentApplication.id == application_id
        )

        if for_update:
            query = query.with_for_update()

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_open_for_athlete(
        self,
        athlete_id: uuid.UUID,
    ) -> TalentApplication | None:
        result = await self.session.execute(
            select(TalentApplication)
            .where(
                TalentApplication.athlete_id == athlete_id,
                TalentApplication.status.in_(("draft", "submitted")),
            )
            .order_by(TalentApplication.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_user_id(
        self,
        user_id: uuid.UUID,
    ) -> list[TalentApplication]:
        result = await self.session.execute(
            select(TalentApplication)
            .where(TalentApplication.user_id == user_id)
            .order_by(TalentApplication.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(
        self,
        application: TalentApplication,
    ) -> TalentApplication:
        await self.session.flush()
        await self.session.refresh(application)
        return application
