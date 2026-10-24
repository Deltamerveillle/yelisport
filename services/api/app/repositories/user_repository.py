"""Repository for SMS application users."""

import uuid
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Profile, User


class UserRepository:
    """Database operations for local SMS users."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        user_id: uuid.UUID,
    ) -> User | None:
        return cast(User | None, await self.session.scalar(
            select(User).where(
                User.id == user_id
            )
        ))

    async def get_by_id_for_update(
        self,
        user_id: uuid.UUID,
    ) -> User | None:
        return cast(User | None, await self.session.scalar(
            select(User)
            .where(
                User.id == user_id
            )
            .with_for_update()
        ))

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        email: str,
    ) -> User:
        user = User(
            id=user_id,
            email=email,
        )
        user.profile = Profile(
            user_id=user_id,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def save(
        self,
        user: User,
    ) -> User:
        await self.session.flush()
        await self.session.refresh(user)
        return user
