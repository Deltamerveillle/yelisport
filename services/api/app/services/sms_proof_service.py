"""Secure SMS Proof verification decisions and audit history."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.athlete_performance import AthletePerformance
from app.models.athlete_performance_verification import (
    AthletePerformanceVerification,
)
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.user_role_repository import UserRoleRepository


class SMSProofService:
    """Verify athletic performances with an auditable decision."""

    ALLOWED_DECISIONS = frozenset(
        {"declared", "documented", "verified"}
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.athletes = AthleteRepository(session)
        self.roles = UserRoleRepository(session)

    async def verify_performance(
        self,
        *,
        performance_id: uuid.UUID,
        verifier_user_id: uuid.UUID,
        decision: str,
        reason: str,
        evidence: dict | None = None,
    ) -> AthletePerformanceVerification:
        """Record a decision and update the performance atomically."""

        role = await self.roles.get_verified_admin_role(
            user_id=verifier_user_id
        )
        if role is None:
            raise ForbiddenError(
                "Only verified SMS administrators can review performances"
            )

        if decision not in self.ALLOWED_DECISIONS:
            raise ValueError("Invalid SMS Proof decision")

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("A verification reason is required")

        if evidence is not None and not isinstance(evidence, dict):
            raise ValueError("Evidence must be a JSON object")

        performance = await self.session.scalar(
            select(AthletePerformance)
            .where(AthletePerformance.id == performance_id)
            .with_for_update()
        )
        if performance is None:
            raise NotFoundError("Athlete performance not found")

        athlete = await self.athletes.get_by_id(
            performance.athlete_id
        )
        if athlete is None:
            raise NotFoundError("Athlete not found")

        if athlete.user_id == verifier_user_id:
            raise ForbiddenError(
                "You cannot verify your own athletic performance"
            )

        verification = AthletePerformanceVerification(
            performance_id=performance.id,
            verifier_user_id=verifier_user_id,
            decision=decision,
            reason=reason.strip(),
            evidence=evidence if evidence is not None else {},
        )

        performance.verification_status = decision
        self.session.add(verification)
        await self.session.flush()

        return verification

    async def list_verifications(
        self,
        *,
        performance_id: uuid.UUID,
        requester_user_id: uuid.UUID,
    ) -> list[AthletePerformanceVerification]:
        """List verification history for authorized SMS administrators."""

        role = await self.roles.get_verified_admin_role(
            user_id=requester_user_id,
        )
        if role is None:
            raise ForbiddenError(
                "Only verified SMS administrators can view verification history"
            )

        performance = await self.session.scalar(
            select(AthletePerformance).where(
                AthletePerformance.id == performance_id
            )
        )
        if performance is None:
            raise NotFoundError("Athlete performance not found")

        result = await self.session.scalars(
            select(AthletePerformanceVerification)
            .where(
                AthletePerformanceVerification.performance_id
                == performance_id
            )
            .order_by(
                AthletePerformanceVerification.created_at.desc(),
                AthletePerformanceVerification.id.desc(),
            )
        )
        return list(result.all())
