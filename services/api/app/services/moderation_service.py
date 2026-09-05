"""Business rules for SMS moderation."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.models.athlete import Athlete
from app.models.discover_video import DiscoverVideo
from app.models.moderation_report import (
    ModerationReport,
    ModerationReportEvent,
)
from app.models.sms_connect_interest import SMSConnectInterest
from app.models.user import User
from app.repositories.discover_video_repository import DiscoverVideoRepository
from app.repositories.moderation_repository import (
    ModerationReportEventRepository,
    ModerationReportRepository,
)
from app.repositories.user_repository import UserRepository
from app.repositories.user_role_repository import (
    UserRoleRepository,
)
from app.schemas.moderation import (
    UserModerationAction,
    DiscoverModerationDecision,
    ModerationReportCreate,
    ModerationTransitionRequest,
)


_ALLOWED_TRANSITIONS = {
    "submitted": {
        "under_review",
        "dismissed",
    },
    "under_review": {
        "resolved",
        "dismissed",
    },
    "resolved": set(),
    "dismissed": set(),
}


class ModerationService:
    """SMS product-facing moderation workflow."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session
        self.reports = ModerationReportRepository(
            session
        )
        self.events = ModerationReportEventRepository(
            session
        )
        self.roles = UserRoleRepository(session)
        self.users = UserRepository(session)
        self.videos = DiscoverVideoRepository(session)

    async def create_report(
        self,
        *,
        reporter_user_id: uuid.UUID,
        data: ModerationReportCreate,
    ) -> ModerationReport:
        await self._validate_resource(
            resource_type=data.resource_type,
            resource_id=data.resource_id,
        )

        if (
            data.resource_type == "user"
            and data.resource_id == reporter_user_id
        ):
            raise ForbiddenError(
                "You cannot report your own user account"
            )

        details = (
            data.details.strip()
            if data.details is not None
            else None
        )

        if details == "":
            details = None

        report = ModerationReport(
            reporter_user_id=reporter_user_id,
            resource_type=data.resource_type,
            resource_id=data.resource_id,
            reason=data.reason,
            details=details,
            status="submitted",
        )

        report = await self.reports.create(report)

        await self.events.create(
            ModerationReportEvent(
                report_id=report.id,
                actor_user_id=reporter_user_id,
                actor_role="user",
                action="submitted",
                from_status=None,
                to_status="submitted",
                note=None,
            )
        )

        return report

    async def list_my_reports(
        self,
        *,
        reporter_user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ModerationReport]:
        return await self.reports.list_for_reporter(
            reporter_user_id=reporter_user_id,
            limit=limit,
            offset=offset,
        )

    async def list_admin_reports(
        self,
        *,
        admin_user_id: uuid.UUID,
        status: str | None = None,
        resource_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ModerationReport]:
        await self._require_admin(admin_user_id)

        return await self.reports.list_for_admin(
            status=status,
            resource_type=resource_type,
            limit=limit,
            offset=offset,
        )

    async def transition_report(
        self,
        *,
        report_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        data: ModerationTransitionRequest,
    ) -> ModerationReport:
        admin_role = await self._require_admin(
            admin_user_id
        )

        report = await self.reports.get_by_id_for_update(
            report_id
        )

        if report is None:
            raise NotFoundError(
                "Moderation report not found"
            )

        from_status = report.status
        to_status = data.status

        allowed = _ALLOWED_TRANSITIONS.get(
            from_status,
            set(),
        )

        if to_status not in allowed:
            raise ConflictError(
                "Invalid moderation status transition: "
                f"{from_status} -> {to_status}"
            )

        note = (
            data.note.strip()
            if data.note is not None
            else None
        )

        if note == "":
            note = None

        report.status = to_status

        await self.events.create(
            ModerationReportEvent(
                report_id=report.id,
                actor_user_id=admin_user_id,
                actor_role=admin_role.role,
                action=to_status,
                from_status=from_status,
                to_status=to_status,
                note=note,
            )
        )

        return await self.reports.save(report)

    async def decide_discover_video(
        self,
        *,
        report_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        data: DiscoverModerationDecision,
    ):
        """Approve or reject a Discover video under review."""

        await self._require_admin(
            admin_user_id
        )

        report = await self.reports.get_by_id_for_update(
            report_id
        )

        if report is None:
            raise NotFoundError(
                "Moderation report not found"
            )

        if report.resource_type != "discover_video":
            raise ConflictError(
                "Moderation report is not for a Discover video"
            )

        if report.status != "under_review":
            raise ConflictError(
                "Discover moderation decision requires "
                "an under-review report"
            )

        video = await self.videos.get_by_id(
            report.resource_id
        )

        if video is None:
            raise NotFoundError(
                "Discover video not found"
            )

        if video.publication_status != "published":
            raise ConflictError(
                "Discover video is not submitted for publication"
            )

        if not video.is_active:
            raise ConflictError(
                "Inactive Discover video cannot be moderated"
            )

        previous_status = report.status
        decision = data.decision
        note = (
            data.note.strip()
            if data.note is not None
            else None
        )

        video.moderation_status = decision
        await self.videos.update(video)

        report.status = "resolved"
        await self.reports.save(report)

        event = ModerationReportEvent(
            report_id=report.id,
            actor_user_id=admin_user_id,
            actor_role="admin",
            action=(
                "discover_approved"
                if decision == "approved"
                else "discover_rejected"
            ),
            from_status=previous_status,
            to_status="resolved",
            note=note,
        )

        await self.events.create(event)

        return video

    async def moderate_user(
        self,
        *,
        report_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        data: UserModerationAction,
    ):
        """Suspend or reactivate a user from an active moderation case."""

        await self._require_admin(
            admin_user_id
        )

        report = await self.reports.get_by_id_for_update(
            report_id
        )

        if report is None:
            raise NotFoundError(
                "Moderation report not found"
            )

        if report.resource_type != "user":
            raise ConflictError(
                "Moderation report is not for a user"
            )

        if report.status != "under_review":
            raise ConflictError(
                "User moderation action requires "
                "an under-review report"
            )

        target_user_id = report.resource_id

        if target_user_id == admin_user_id:
            raise ForbiddenError(
                "Administrator cannot suspend or reactivate self"
            )

        user = await self.users.get_by_id_for_update(
            target_user_id
        )

        if user is None:
            raise NotFoundError(
                "User not found"
            )

        note = (
            data.note.strip()
            if data.note is not None
            else None
        )

        if data.action == "suspend":
            if not user.is_active:
                raise ConflictError(
                    "User is already suspended"
                )

            user.is_active = False
            event_action = "user_suspended"

        else:
            if user.is_active:
                raise ConflictError(
                    "User is already active"
                )

            user.is_active = True
            event_action = "user_reactivated"

        await self.users.save(user)

        report.status = "resolved"
        await self.reports.save(report)

        event = ModerationReportEvent(
            report_id=report.id,
            actor_user_id=admin_user_id,
            actor_role="admin",
            action=event_action,
            from_status="under_review",
            to_status="resolved",
            note=note,
        )

        await self.events.create(event)

        return user

    async def list_report_events(
        self,
        *,
        report_id: uuid.UUID,
        admin_user_id: uuid.UUID,
    ) -> Sequence[ModerationReportEvent]:
        await self._require_admin(admin_user_id)

        report = await self.reports.get_by_id(
            report_id
        )

        if report is None:
            raise NotFoundError(
                "Moderation report not found"
            )

        return await self.events.list_for_report(
            report_id
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

    async def _validate_resource(
        self,
        *,
        resource_type: str,
        resource_id: uuid.UUID,
    ) -> None:
        model = {
            "user": User,
            "athlete": Athlete,
            "discover_video": DiscoverVideo,
            "sms_connect_interest": SMSConnectInterest,
        }.get(resource_type)

        if model is None:
            raise NotFoundError(
                "Moderation resource not found"
            )

        existing_id = await self.session.scalar(
            select(model.id).where(
                model.id == resource_id
            )
        )

        if existing_id is None:
            raise NotFoundError(
                "Moderation resource not found"
            )
