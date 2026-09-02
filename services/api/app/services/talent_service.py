"""Business rules for SMS Talent."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.talent_application import TalentApplication
from app.models.talent_evaluation import TalentEvaluation
from app.models.talent_submission_item import TalentSubmissionItem
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.talent_application_repository import (
    TalentApplicationRepository,
)
from app.repositories.talent_evaluation_repository import (
    TalentEvaluationRepository,
)
from app.repositories.talent_submission_item_repository import (
    TalentSubmissionItemRepository,
)
from app.repositories.user_role_repository import UserRoleRepository
from app.services.subscription_service import SubscriptionService


class TalentService:
    """Domain service enforcing independent SMS Talent evaluations."""

    MAX_EVALUATORS = 3
    SMS_EVALUATOR_ROLE = "sms_evaluator"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.athletes = AthleteRepository(session)
        self.applications = TalentApplicationRepository(session)
        self.evaluations = TalentEvaluationRepository(session)
        self.submission_items = TalentSubmissionItemRepository(session)
        self.user_roles = UserRoleRepository(session)
        self.subscription_service = SubscriptionService(session)

    async def create_application(
        self,
        *,
        athlete_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> TalentApplication:
        """
        Create a paid SMS Talent evaluation application.

        Payment grants access to the evaluation service only.
        It never influences scores, recommendations, or rankings.
        """

        athlete = await self.athletes.get_by_id(
            athlete_id,
            for_update=True,
        )

        if athlete is None:
            raise ValueError("Athlete not found")

        if athlete.user_id != user_id:
            raise ValueError(
                "User cannot create Talent application for another athlete"
            )

        has_access = await self.subscription_service.has_premium_access(
            user_id
        )

        if not has_access:
            raise ValueError(
                "Active premium access is required for SMS Talent"
            )

        existing_application = (
            await self.applications.get_open_for_athlete(
                athlete.id
            )
        )

        if existing_application is not None:
            raise ValueError(
                "Athlete already has an open SMS Talent application"
            )

        application = TalentApplication(
            athlete_id=athlete.id,
            user_id=user_id,
            sport_id=athlete.sport_id,
            status="draft",
        )

        return await self.applications.create(application)

    async def add_submission_item(
        self,
        *,
        application_id: uuid.UUID,
        user_id: uuid.UUID,
        item_type: str,
        resource_url: str,
        title: str | None = None,
        description: str | None = None,
        metadata_json: dict | None = None,
    ) -> TalentSubmissionItem:
        application = await self.applications.get_by_id(application_id)

        if application is None:
            raise ValueError("Talent application not found")

        if application.user_id != user_id:
            raise ValueError(
                "User cannot modify another Talent application"
            )

        if application.status != "draft":
            raise ValueError(
                "Talent application materials are locked after submission"
            )

        item = TalentSubmissionItem(
            application_id=application.id,
            item_type=item_type,
            resource_url=resource_url,
            title=title,
            description=description,
            metadata_json=metadata_json,
        )

        return await self.submission_items.create(item)

    async def list_submission_items(
        self,
        *,
        application_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        application = await self.applications.get_by_id(application_id)

        if application is None:
            raise ValueError("Talent application not found")

        if application.user_id != user_id:
            raise ValueError(
                "User cannot access another Talent application"
            )

        return await self.submission_items.list_by_application_id(
            application_id
        )

    async def delete_submission_item(
        self,
        *,
        application_id: uuid.UUID,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        application = await self.applications.get_by_id(application_id)

        if application is None:
            raise ValueError("Talent application not found")

        if application.user_id != user_id:
            raise ValueError(
                "User cannot modify another Talent application"
            )

        if application.status != "draft":
            raise ValueError(
                "Talent application materials are locked after submission"
            )

        item = await self.submission_items.get_by_id(item_id)

        if item is None or item.application_id != application_id:
            raise ValueError("Talent submission item not found")

        await self.submission_items.delete(item)

    async def submit_application(
        self,
        *,
        application_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> TalentApplication:
        application = await self.applications.get_by_id(
            application_id,
            for_update=True,
        )

        if application is None:
            raise ValueError("Talent application not found")

        if application.user_id != user_id:
            raise ValueError(
                "User cannot submit another Talent application"
            )

        if application.status != "draft":
            raise ValueError(
                "Talent application is not in draft status"
            )

        items = await self.submission_items.list_by_application_id(
            application_id
        )

        if not items:
            raise ValueError(
                "Talent application requires at least one submission item"
            )

        application.status = "submitted"
        application.submitted_at = datetime.now(timezone.utc)

        return await self.applications.update(application)

    async def assign_evaluator(
        self,
        *,
        application_id: uuid.UUID,
        evaluator_user_id: uuid.UUID,
    ) -> TalentEvaluation:
        application = await self.applications.get_by_id(
            application_id,
            for_update=True,
        )

        if application is None:
            raise ValueError("Talent application not found")

        if application.status == "completed":
            raise ValueError("Talent application already completed")

        if application.status != "submitted":
            raise ValueError(
                "Talent application must be submitted before evaluator assignment"
            )

        if evaluator_user_id == application.user_id:
            raise ValueError("Athlete cannot evaluate own application")

        evaluator_role = await self.user_roles.get_by_user_and_role(
            user_id=evaluator_user_id,
            role=self.SMS_EVALUATOR_ROLE,
        )

        if (
            evaluator_role is None
            or not evaluator_role.is_active
            or not evaluator_role.is_verified
        ):
            raise ValueError(
                "Evaluator must be an active and verified SMS evaluator"
            )

        existing = await self.evaluations.get_for_evaluator(
            application_id=application_id,
            evaluator_user_id=evaluator_user_id,
        )

        if existing is not None:
            raise ValueError(
                "Evaluator already assigned to this application"
            )

        evaluator_count = await self.evaluations.count_for_application(
            application_id
        )

        if evaluator_count >= self.MAX_EVALUATORS:
            raise ValueError(
                "Talent application already has three evaluators"
            )

        evaluation = TalentEvaluation(
            application_id=application_id,
            evaluator_user_id=evaluator_user_id,
            status="assigned",
        )

        return await self.evaluations.create(evaluation)

    async def get_evaluation_for_evaluator(
        self,
        *,
        application_id: uuid.UUID,
        evaluator_user_id: uuid.UUID,
    ) -> TalentEvaluation:
        """
        Return only the requesting evaluator's own evaluation.

        This method deliberately does not expose the evaluations
        belonging to the two other evaluators.
        """

        evaluation = await self.evaluations.get_for_evaluator(
            application_id=application_id,
            evaluator_user_id=evaluator_user_id,
        )

        if evaluation is None:
            raise ValueError("Evaluator not assigned to this application")

        return evaluation

    async def submit_evaluation(
        self,
        *,
        application_id: uuid.UUID,
        evaluator_user_id: uuid.UUID,
        scores: dict,
        overall_score: Decimal,
        recommendation: str | None = None,
        comments: str | None = None,
    ) -> TalentEvaluation:
        application = await self.applications.get_by_id(
            application_id,
            for_update=True,
        )

        if application is None:
            raise ValueError("Talent application not found")

        if application.status == "completed":
            raise ValueError("Talent application already completed")

        evaluation = await self.evaluations.get_for_evaluator(
            application_id=application_id,
            evaluator_user_id=evaluator_user_id,
        )

        if evaluation is None:
            raise ValueError("Evaluator not assigned to this application")

        if evaluation.status == "submitted":
            raise ValueError("Talent evaluation is locked")

        if overall_score < Decimal("0"):
            raise ValueError("Overall score cannot be below zero")

        if overall_score > Decimal("100"):
            raise ValueError("Overall score cannot exceed 100")

        if not scores:
            raise ValueError("Evaluation scores are required")

        now = datetime.now(timezone.utc)

        evaluation.scores = scores
        evaluation.overall_score = overall_score
        evaluation.recommendation = recommendation
        evaluation.comments = comments
        evaluation.status = "submitted"
        evaluation.submitted_at = now

        evaluation = await self.evaluations.update(evaluation)

        submitted_count = (
            await self.evaluations.count_submitted_for_application(
                application_id
            )
        )

        if submitted_count >= self.MAX_EVALUATORS:
            application.status = "completed"
            application.completed_at = now
            await self.applications.update(application)

        return evaluation

    async def get_completed_evaluations(
        self,
        *,
        application_id: uuid.UUID,
    ) -> list[TalentEvaluation]:
        """
        Return all evaluations only after the Talent process is complete.

        This prevents one evaluator from seeing another evaluator's
        scores while independent evaluation is still in progress.
        """

        application = await self.applications.get_by_id(application_id)

        if application is None:
            raise ValueError("Talent application not found")

        if application.status != "completed":
            raise ValueError(
                "Talent evaluations remain confidential until completion"
            )

        evaluations = await self.evaluations.list_for_application(
            application_id
        )

        if len(evaluations) != self.MAX_EVALUATORS:
            raise ValueError(
                "Completed Talent application must have three evaluations"
            )

        if any(
            evaluation.status != "submitted"
            for evaluation in evaluations
        ):
            raise ValueError(
                "All Talent evaluations must be submitted"
            )

        return evaluations
