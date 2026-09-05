"""Repository for SMS application users."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Database operations for local SMS users."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        user_id: uuid.UUID,
    ) -> User | None:
        return await self.session.scalar(
            select(User).where(
                User.id == user_id
            )
        )

    async def get_by_id_for_update(
        self,
        user_id: uuid.UUID,
    ) -> User | None:
        return await self.session.scalar(
            select(User)
            .where(
                User.id == user_id
            )
            .with_for_update()
        )

    async def save(
        self,
        user: User,
    ) -> User:
        await self.session.flush()
        await self.session.refresh(user)
        return user
