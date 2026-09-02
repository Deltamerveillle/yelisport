"""Repository for SMS Talent evaluations."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.talent_evaluation import TalentEvaluation


class TalentEvaluationRepository:
    """Persistence operations for independent SMS Talent evaluations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        evaluation: TalentEvaluation,
    ) -> TalentEvaluation:
        self.session.add(evaluation)
        await self.session.flush()
        await self.session.refresh(evaluation)
        return evaluation

    async def get_by_id(
        self,
        evaluation_id: uuid.UUID,
    ) -> TalentEvaluation | None:
        result = await self.session.execute(
            select(TalentEvaluation).where(
                TalentEvaluation.id == evaluation_id
            )
        )
        return result.scalar_one_or_none()

    async def get_for_evaluator(
        self,
        *,
        application_id: uuid.UUID,
        evaluator_user_id: uuid.UUID,
    ) -> TalentEvaluation | None:
        result = await self.session.execute(
            select(TalentEvaluation).where(
                TalentEvaluation.application_id == application_id,
                TalentEvaluation.evaluator_user_id == evaluator_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def count_for_application(
        self,
        application_id: uuid.UUID,
    ) -> int:
        result = await self.session.execute(
            select(func.count(TalentEvaluation.id)).where(
                TalentEvaluation.application_id == application_id
            )
        )
        return int(result.scalar_one())

    async def count_submitted_for_application(
        self,
        application_id: uuid.UUID,
    ) -> int:
        result = await self.session.execute(
            select(func.count(TalentEvaluation.id)).where(
                TalentEvaluation.application_id == application_id,
                TalentEvaluation.status == "submitted",
            )
        )
        return int(result.scalar_one())

    async def list_for_application(
        self,
        application_id: uuid.UUID,
    ) -> list[TalentEvaluation]:
        result = await self.session.execute(
            select(TalentEvaluation)
            .where(
                TalentEvaluation.application_id == application_id
            )
            .order_by(TalentEvaluation.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_evaluator(
        self,
        evaluator_user_id: uuid.UUID,
    ) -> list[TalentEvaluation]:
        result = await self.session.execute(
            select(TalentEvaluation)
            .where(
                TalentEvaluation.evaluator_user_id == evaluator_user_id
            )
            .order_by(TalentEvaluation.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(
        self,
        evaluation: TalentEvaluation,
    ) -> TalentEvaluation:
        await self.session.flush()
        await self.session.refresh(evaluation)
        return evaluation
