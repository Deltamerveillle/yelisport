"""Repository for SMS multi-role authorization."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_role import UserRole


class UserRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user_and_role(
        self,
        *,
        user_id: uuid.UUID,
        role: str,
    ) -> UserRole | None:
        """Return the role only when the owning user account is active."""
        return await self.session.scalar(
            select(UserRole)
            .join(
                User,
                User.id == UserRole.user_id,
            )
            .where(
                UserRole.user_id == user_id,
                UserRole.role == role,
                User.is_active.is_(True),
            )
        )

    async def get_verified_professional_role(
        self,
        *,
        user_id: uuid.UUID,
    ) -> UserRole | None:
        """Return one active verified SMS Connect role."""

        return await self.session.scalar(
            select(UserRole)
            .join(
                User,
                User.id == UserRole.user_id,
            )
            .where(
                UserRole.user_id == user_id,
                UserRole.role.in_(
                    (
                        "club",
                        "recruiter",
                        "federation",
                    )
                ),
                UserRole.is_active.is_(True),
                UserRole.is_verified.is_(True),
                User.is_active.is_(True),
            )
            .order_by(UserRole.created_at.asc())
        )


    async def get_verified_admin_role(
        self,
        *,
        user_id: uuid.UUID,
    ) -> UserRole | None:
        """Return an active verified SMS administrator role."""

        return await self.session.scalar(
            select(UserRole)
            .join(
                User,
                User.id == UserRole.user_id,
            )
            .where(
                UserRole.user_id == user_id,
                UserRole.role == "admin",
                UserRole.is_active.is_(True),
                UserRole.is_verified.is_(True),
                User.is_active.is_(True),
            )
        )
