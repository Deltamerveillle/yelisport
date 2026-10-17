"""Fail-closed configuration checks before any database access."""

import uuid
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import ApplicationError
from app.services.free_test_pilot_service import FreeTestPilotService
from tests.api.test_payments import plan


@pytest.mark.parametrize(
    "environment,enabled",
    [
        ("production", True),
        ("production", False),
        ("development", False),
        ("test", False),
        ("staging", False),
    ],
)
async def test_disabled_before_database(environment, enabled):
    session = AsyncMock()
    settings = Settings(app_env=environment, sms_free_test_pilot_enabled=enabled)
    with pytest.raises(ApplicationError) as error:
        await FreeTestPilotService(session, settings).activate(uuid.uuid4())
    assert error.value.code == "pilot_disabled"
    session.execute.assert_not_called()


@pytest.mark.parametrize("plans", [[], [plan(entitlements={"priority_visibility": True})]])
async def test_invalid_catalogue_fails_closed(plans):
    session = AsyncMock()
    settings = Settings(
        sms_free_test_pilot_enabled=True,
        sms_free_test_pilot_plan_code="test_offer_v1",
        sms_commercial_plans=plans,
    )
    with pytest.raises(ApplicationError) as error:
        await FreeTestPilotService(session, settings).activate(uuid.uuid4())
    assert error.value.code == "pilot_unavailable"
    session.execute.assert_not_called()


@pytest.mark.parametrize("days", [0, -1, 31])
def test_duration_bounded(days):
    with pytest.raises(ValidationError):
        Settings(sms_free_test_pilot_duration_days=days)
