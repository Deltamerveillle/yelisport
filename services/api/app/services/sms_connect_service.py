"""Business rules for SMS Connect."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.models.sms_connect_athlete_response_event import SMSConnectAthleteResponseEvent
from app.models.sms_connect_interest import (
    SMSConnectInterest,
)
from app.models.sms_connect_interest_event import (
    SMSConnectInterestEvent,
)
from app.models.sms_connect_opportunity import SMSConnectOpportunity, SMSConnectOpportunityEvent
from app.models.user_role import UserRole
from app.repositories.athlete_passport_repository import (
    AthletePassportRepository,
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
from app.repositories.sms_connect_opportunity_repository import SMSConnectOpportunityRepository
from app.repositories.user_role_repository import (
    UserRoleRepository,
)
from app.schemas.sms_connect import (
    SMSConnectAthleteResponseRequest,
    SMSConnectInterestCreate,
    SMSConnectOpportunityTransitionRequest,
    SMSConnectTransitionRequest,
)
from app.services.notification_service import (
    NotificationService,
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
        self.opportunities = SMSConnectOpportunityRepository(session)
        self.athletes = AthleteRepository(
            session
        )
        self.passports = AthletePassportRepository(
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

        passport = await self.passports.get_by_athlete_id(
            athlete.id
        )

        if (
            passport is None
            or not passport.available_for_opportunities
        ):
            raise ForbiddenError(
                "Athlete is not available for opportunities"
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

    async def respond_to_interest(
        self,
        *,
        interest_id: uuid.UUID,
        athlete_user_id: uuid.UUID,
        data: SMSConnectAthleteResponseRequest,
    ) -> SMSConnectInterest:
        """Record a private athlete decision without changing SMS administrative state."""
        interest = await self.interests.get_by_id_for_update(interest_id)
        if interest is None:
            raise NotFoundError("SMS Connect interest not found")
        athlete = await self.athletes.get_by_id(interest.athlete_id)
        if athlete is None:
            raise NotFoundError("Athlete not found")
        if athlete.user_id != athlete_user_id:
            raise ForbiddenError("Only the athlete owner can respond to this opportunity")
        if interest.status != "delivered":
            raise ConflictError("Only delivered SMS Connect interests can receive a response")
        if interest.athlete_response == data.athlete_response:
            return interest

        now = datetime.now(UTC)
        event = SMSConnectAthleteResponseEvent(
            interest_id=interest.id,
            actor_user_id=athlete_user_id,
            from_response=interest.athlete_response,
            to_response=data.athlete_response,
            created_at=now,
        )
        interest.athlete_response = data.athlete_response
        interest.athlete_responded_at = now
        await self.interests.add_athlete_response_event(event)
        await self._sync_opportunity(interest, athlete_user_id, now)
        return await self.interests.save(interest)

    async def _sync_opportunity(
        self, interest: SMSConnectInterest, actor_user_id: uuid.UUID, now: datetime
    ) -> None:
        # Caller already holds the interest lock: all writers lock interest, then opportunity.
        opportunity = await self.opportunities.get_for_interest_for_update(interest.id)
        previous = opportunity.status if opportunity is not None else None
        if opportunity is None and interest.athlete_response == "interested":
            opportunity = await self.opportunities.create(SMSConnectOpportunity(
                interest_id=interest.id, status="active", opened_at=now,
            ))
            source = "athlete_consent"
        elif opportunity is not None and previous == "withdrawn" and (
            interest.athlete_response == "interested"
        ):
            opportunity.status = "active"
            opportunity.closed_at = None
            source = "athlete_reactivation"
        elif opportunity is not None and previous in {"active", "progressing"} and (
            interest.athlete_response == "declined"
        ):
            opportunity.status = "withdrawn"
            opportunity.closed_at = now
            source = "athlete_withdrawal"
        else:
            # Completed commercial outcomes are never rewritten by a later decision.
            return
        await self.opportunities.add_event(SMSConnectOpportunityEvent(
            opportunity_id=opportunity.id, actor_user_id=actor_user_id,
            from_status=previous, to_status=opportunity.status, source=source, created_at=now,
        ))

    async def list_athlete_opportunities(
        self, athlete_user_id: uuid.UUID
    ) -> Sequence[RowMapping]:
        return await self.opportunities.list_for_athlete(athlete_user_id)

    async def list_my_opportunities(
        self, requester_user_id: uuid.UUID
    ) -> Sequence[RowMapping]:
        return await self.opportunities.list_for_requester(requester_user_id)

    async def transition_opportunity(
        self, *, opportunity_id: uuid.UUID, admin_user_id: uuid.UUID,
        data: SMSConnectOpportunityTransitionRequest,
    ) -> RowMapping:
        await self._require_admin(admin_user_id)
        opportunity = await self.opportunities.get_by_id(opportunity_id)
        if opportunity is None:
            raise NotFoundError("SMS Connect opportunity not found")
        await self.interests.get_by_id_for_update(opportunity.interest_id)
        opportunity = await self.opportunities.get_for_interest_for_update(opportunity.interest_id)
        if opportunity is None:
            raise NotFoundError("SMS Connect opportunity not found")
        allowed = {
            "active": {"progressing", "unsuccessful"},
            "progressing": {"successful", "unsuccessful"},
        }
        previous = opportunity.status
        if data.status not in allowed.get(previous, set()):
            raise ConflictError("Invalid SMS Connect opportunity transition")
        now = datetime.now(UTC)
        opportunity.status = data.status
        if data.status in {"successful", "unsuccessful"}:
            opportunity.closed_at = now
        await self.opportunities.add_event(SMSConnectOpportunityEvent(
            opportunity_id=opportunity.id, actor_user_id=admin_user_id,
            from_status=previous, to_status=data.status, source="sms_admin", created_at=now,
        ))
        return await self.opportunities.get_response(opportunity.id)

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

        now = datetime.now(UTC)

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
    ) -> UserRole:
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
