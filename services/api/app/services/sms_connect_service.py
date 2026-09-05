"""Business rules for SMS Connect."""

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.models.sms_connect_interest import (
    SMSConnectInterest,
)
from app.models.sms_connect_interest_event import (
    SMSConnectInterestEvent,
)
from app.repositories.athlete_repository import (
    AthleteRepository,
)
from app.repositories.sms_connect_interest_event_repository import (
    SMSConnectInterestEventRepository,
)
from app.repositories.sms_connect_interest_repository import (
    SMSConnectInterestRepository,
)
from app.repositories.user_role_repository import (
    UserRoleRepository,
)
from app.services.notification_service import (
    NotificationService,
)
from app.schemas.sms_connect import (
    SMSConnectInterestCreate,
    SMSConnectTransitionRequest,
)


_ALLOWED_TRANSITIONS = {
    "submitted": {"under_review"},
    "under_review": {
        "approved",
        "rejected",
    },
    "approved": {"delivered"},
    "delivered": {"closed"},
    "rejected": set(),
    "closed": set(),
}


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
        self.events = (
            SMSConnectInterestEventRepository(
                session
            )
        )
        self.notification_service = (
            NotificationService(
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

    async def list_athlete_inbox(
        self,
        athlete_user_id: uuid.UUID,
    ) -> Sequence[SMSConnectInterest]:
        """
        Return only interests formally delivered by SMS.

        Approval alone never exposes an interest to the athlete.
        """

        return (
            await self.interests
            .list_for_athlete_user(
                athlete_user_id
            )
        )

    async def list_admin_interests(
        self,
        *,
        admin_user_id: uuid.UUID,
        interest_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[SMSConnectInterest]:
        await self._require_admin(
            admin_user_id
        )

        return await self.interests.list_for_admin(
            interest_status=interest_status,
            limit=limit,
            offset=offset,
        )

    async def transition_interest(
        self,
        *,
        interest_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        data: SMSConnectTransitionRequest,
    ) -> SMSConnectInterest:
        admin_role = await self._require_admin(
            admin_user_id
        )

        interest = (
            await self.interests
            .get_by_id_for_update(
                interest_id
            )
        )

        if interest is None:
            raise NotFoundError(
                "SMS Connect interest not found"
            )

        from_status = interest.status
        to_status = data.status

        allowed = _ALLOWED_TRANSITIONS.get(
            from_status,
            set(),
        )

        if to_status not in allowed:
            raise ConflictError(
                "Invalid SMS Connect status transition: "
                f"{from_status} -> {to_status}"
            )

        now = datetime.now(timezone.utc)

        interest.status = to_status

        if to_status in {
            "approved",
            "rejected",
        }:
            interest.reviewed_at = now

        if to_status == "delivered":
            interest.delivered_at = now

            athlete = (
                await self.athletes.get_by_id(
                    interest.athlete_id
                )
            )

            if athlete is None:
                raise NotFoundError(
                    "Athlete not found"
                )

            await self.notification_service.create_sms_connect_delivery(
                recipient_user_id=athlete.user_id,
                interest_id=interest.id,
                organization_name=(
                    interest.organization_name
                ),
            )

        event = SMSConnectInterestEvent(
            interest_id=interest.id,
            actor_user_id=admin_user_id,
            actor_role=admin_role.role,
            from_status=from_status,
            to_status=to_status,
            note=(
                data.note.strip()
                if data.note
                else None
            ),
        )

        await self.events.create(event)

        return await self.interests.save(
            interest
        )

    async def list_interest_events(
        self,
        *,
        interest_id: uuid.UUID,
        admin_user_id: uuid.UUID,
    ) -> Sequence[SMSConnectInterestEvent]:
        await self._require_admin(
            admin_user_id
        )

        interest = await self.interests.get_by_id(
            interest_id
        )

        if interest is None:
            raise NotFoundError(
                "SMS Connect interest not found"
            )

        return await self.events.list_for_interest(
            interest_id
        )

    async def _require_admin(
        self,
        user_id: uuid.UUID,
    ):
        role = (
            await self.roles
            .get_verified_admin_role(
                user_id=user_id
            )
        )

        if role is None:
            raise ForbiddenError(
                "A verified SMS administrator role "
                "is required"
            )

        return role
