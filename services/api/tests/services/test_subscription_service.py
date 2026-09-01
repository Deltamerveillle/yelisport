"""Tests for SMS subscription business rules."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.subscription_service import SubscriptionService


@pytest.mark.asyncio
async def test_no_subscription_means_no_premium_access() -> None:
    service = SubscriptionService.__new__(SubscriptionService)
    service.subscriptions = SimpleNamespace(
        get_current_for_user=AsyncMock(return_value=None)
    )

    user_id = uuid.uuid4()

    assert await service.get_current_subscription(user_id) is None
    assert await service.has_premium_access(user_id) is False


@pytest.mark.asyncio
async def test_active_premium_subscription_grants_access() -> None:
    subscription = SimpleNamespace(
        status="active",
        plan_code="premium",
        current_period_end=datetime.now(UTC) + timedelta(days=30),
    )

    service = SubscriptionService.__new__(SubscriptionService)
    service.subscriptions = SimpleNamespace(
        get_current_for_user=AsyncMock(return_value=subscription)
    )

    user_id = uuid.uuid4()

    assert await service.get_current_subscription(user_id) is subscription
    assert await service.has_premium_access(user_id) is True


@pytest.mark.asyncio
async def test_trialing_paid_subscription_grants_access() -> None:
    subscription = SimpleNamespace(
        status="trialing",
        plan_code="talent",
        current_period_end=datetime.now(UTC) + timedelta(days=7),
    )

    service = SubscriptionService.__new__(SubscriptionService)
    service.subscriptions = SimpleNamespace(
        get_current_for_user=AsyncMock(return_value=subscription)
    )

    user_id = uuid.uuid4()

    assert await service.has_premium_access(user_id) is True


@pytest.mark.asyncio
async def test_free_subscription_does_not_grant_premium_access() -> None:
    subscription = SimpleNamespace(
        status="active",
        plan_code="free",
        current_period_end=datetime.now(UTC) + timedelta(days=30),
    )

    service = SubscriptionService.__new__(SubscriptionService)
    service.subscriptions = SimpleNamespace(
        get_current_for_user=AsyncMock(return_value=subscription)
    )

    user_id = uuid.uuid4()

    assert await service.has_premium_access(user_id) is False


@pytest.mark.asyncio
async def test_expired_subscription_does_not_grant_access() -> None:
    subscription = SimpleNamespace(
        status="active",
        plan_code="premium",
        current_period_end=datetime.now(UTC) - timedelta(seconds=1),
    )

    service = SubscriptionService.__new__(SubscriptionService)
    service.subscriptions = SimpleNamespace(
        get_current_for_user=AsyncMock(return_value=subscription)
    )

    user_id = uuid.uuid4()

    assert await service.get_current_subscription(user_id) is None
    assert await service.has_premium_access(user_id) is False


@pytest.mark.asyncio
async def test_subscription_without_end_date_can_be_active() -> None:
    subscription = SimpleNamespace(
        status="active",
        plan_code="premium",
        current_period_end=None,
    )

    service = SubscriptionService.__new__(SubscriptionService)
    service.subscriptions = SimpleNamespace(
        get_current_for_user=AsyncMock(return_value=subscription)
    )

    user_id = uuid.uuid4()

    assert await service.has_premium_access(user_id) is True


@pytest.mark.asyncio
async def test_history_is_requested_for_given_user_only() -> None:
    expected = [SimpleNamespace(id=uuid.uuid4())]

    repository = SimpleNamespace(
        list_by_user_id=AsyncMock(return_value=expected)
    )

    service = SubscriptionService.__new__(SubscriptionService)
    service.subscriptions = repository

    user_id = uuid.uuid4()

    result = await service.list_user_subscriptions(user_id)

    assert result == expected
    repository.list_by_user_id.assert_awaited_once_with(user_id)
