"""Tests for authenticated local-user enforcement."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.dependencies import auth as auth_dependency
from app.core.exceptions import ApplicationError
from app.schemas.auth import AuthUser


USER_ID = uuid.uuid4()


class FakeAuthService:
    def user_from_token(self, token):
        assert token == "valid-token"

        return AuthUser(
            id=str(USER_ID),
            email="user@example.com",
        )


@pytest.mark.asyncio
async def test_active_local_user_is_authenticated(
    monkeypatch,
):
    repository = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=SimpleNamespace(
                id=USER_ID,
                is_active=True,
            )
        )
    )

    monkeypatch.setattr(
        auth_dependency,
        "UserRepository",
        lambda session: repository,
    )

    result = await auth_dependency.get_current_user(
        credentials=SimpleNamespace(
            credentials="valid-token"
        ),
        service=FakeAuthService(),
        session=SimpleNamespace(),
    )

    assert result.id == str(USER_ID)

    repository.get_by_id.assert_awaited_once_with(
        USER_ID
    )


@pytest.mark.asyncio
async def test_suspended_local_user_is_rejected(
    monkeypatch,
):
    repository = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=SimpleNamespace(
                id=USER_ID,
                is_active=False,
            )
        )
    )

    monkeypatch.setattr(
        auth_dependency,
        "UserRepository",
        lambda session: repository,
    )

    with pytest.raises(
        ApplicationError
    ) as exc_info:
        await auth_dependency.get_current_user(
            credentials=SimpleNamespace(
                credentials="valid-token"
            ),
            service=FakeAuthService(),
            session=SimpleNamespace(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "account_suspended"


@pytest.mark.asyncio
async def test_missing_local_user_is_rejected(
    monkeypatch,
):
    repository = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=None
        )
    )

    monkeypatch.setattr(
        auth_dependency,
        "UserRepository",
        lambda session: repository,
    )

    with pytest.raises(
        ApplicationError
    ) as exc_info:
        await auth_dependency.get_current_user(
            credentials=SimpleNamespace(
                credentials="valid-token"
            ),
            service=FakeAuthService(),
            session=SimpleNamespace(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "local_user_not_found"
