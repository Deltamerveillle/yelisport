"""Repositories for SMS moderation reports and audit events."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.moderation_report import (
    ModerationReport,
    ModerationReportEvent,
)


class ModerationReportRepository:
    """Database access for moderation reports."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        report: ModerationReport,
    ) -> ModerationReport:
        self.session.add(report)
        await self.session.flush()
        await self.session.refresh(report)
        return report

    async def get_by_id(
        self,
        report_id: uuid.UUID,
    ) -> ModerationReport | None:
        return await self.session.scalar(
            select(ModerationReport).where(
                ModerationReport.id == report_id
            )
        )

    async def get_by_id_for_update(
        self,
        report_id: uuid.UUID,
    ) -> ModerationReport | None:
        return await self.session.scalar(
            select(ModerationReport)
            .where(
                ModerationReport.id == report_id
            )
            .with_for_update()
        )

    async def get_open_publication_review(
        self,
        *,
        resource_id: uuid.UUID,
    ) -> ModerationReport | None:
        """Return the current open Discover publication review, if any."""

        return await self.session.scalar(
            select(ModerationReport)
            .where(
                ModerationReport.resource_type
                == "discover_video",
                ModerationReport.resource_id
                == resource_id,
                ModerationReport.origin
                == "publication_review",
                ModerationReport.status.in_(
                    ("submitted", "under_review")
                ),
            )
            .order_by(
                ModerationReport.created_at.asc(),
                ModerationReport.id.asc(),
            )
            .limit(1)
        )

    async def list_for_reporter(
        self,
        *,
        reporter_user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ModerationReport]:
        result = await self.session.execute(
            select(ModerationReport)
            .where(
                ModerationReport.reporter_user_id
                == reporter_user_id,
                ModerationReport.origin
                == "user_report",
            )
            .order_by(
                ModerationReport.created_at.desc(),
                ModerationReport.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def list_for_admin(
        self,
        *,
        status: str | None = None,
        resource_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ModerationReport]:
        query = select(ModerationReport)

        if status is not None:
            query = query.where(
                ModerationReport.status == status
            )

        if resource_type is not None:
            query = query.where(
                ModerationReport.resource_type
                == resource_type
            )

        result = await self.session.execute(
            query.order_by(
                ModerationReport.created_at.asc(),
                ModerationReport.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return result.scalars().all()

    async def save(
        self,
        report: ModerationReport,
    ) -> ModerationReport:
        await self.session.flush()
        await self.session.refresh(report)
        return report


class ModerationReportEventRepository:
    """Database access for immutable moderation audit events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        event: ModerationReportEvent,
    ) -> ModerationReportEvent:
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def list_for_report(
        self,
        report_id: uuid.UUID,
    ) -> Sequence[ModerationReportEvent]:
        result = await self.session.execute(
            select(ModerationReportEvent)
            .where(
                ModerationReportEvent.report_id
                == report_id
            )
            .order_by(
                ModerationReportEvent.created_at.asc(),
                ModerationReportEvent.id.asc(),
            )
        )

        return result.scalars().all()
