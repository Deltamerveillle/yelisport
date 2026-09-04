"""Business rules for SMS Connect."""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ForbiddenError,
    NotFoundError,
)
from app.models.sms_connect_interest import (
    SMSConnectInterest,
)
from app.repositories.athlete_repository import (
    AthleteRepository,
)
from app.repositories.sms_connect_interest_repository import (
    SMSConnectInterestRepository,
)
from app.repositories.user_role_repository import (
    UserRoleRepository,
)
from app.schemas.sms_connect import (
    SMSConnectInterestCreate,
)


class SMSConnectService:
    """Secure professional-to-athlete contact workflow."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.athletes = AthleteRepository(
            session
        )
        self.roles = UserRoleRepository(
            session
        )
        self.interests = (
            SMSConnectInterestRepository(
                session
            )
        )

    async def create_interest(
        self,
        *,
        athlete_id: uuid.UUID,
        requester_user_id: uuid.UUID,
        data: SMSConnectInterestCreate,
    ) -> SMSConnectInterest:
        athlete = await self.athletes.get_by_id(
            athlete_id
        )

        if athlete is None:
            raise NotFoundError(
                "Athlete not found"
            )

        if athlete.user_id == requester_user_id:
            raise ForbiddenError(
                "Athletes cannot submit professional "
                "interest to themselves"
            )

        role = (
            await self.roles
            .get_verified_professional_role(
                user_id=requester_user_id
            )
        )

        if role is None:
            raise ForbiddenError(
                "A verified club, recruiter or "
                "federation role is required "
                "to contact an athlete"
            )

        interest = SMSConnectInterest(
            athlete_id=athlete.id,
            requester_user_id=(
                requester_user_id
            ),
            requester_role=role.role,
            interest_type=data.interest_type,
            organization_name=(
                data.organization_name.strip()
            ),
            subject=data.subject.strip(),
            message=data.message.strip(),
            status="submitted",
        )

        return await self.interests.create(
            interest
        )

    async def list_my_interests(
        self,
        requester_user_id: uuid.UUID,
    ) -> Sequence[SMSConnectInterest]:
        return (
            await self.interests
            .list_for_requester(
                requester_user_id
            )
        )
