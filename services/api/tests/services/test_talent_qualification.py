"""Tests for SMS Talent qualification and service integration."""

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.talent_qualification import qualify_talent
from app.services.talent_service import TalentService


@pytest.mark.parametrize(
    "scores,expected",
    [
        ([75, 68, 82], "eligible_for_coaching"),
        ([Decimal("50.01"), 65, 90], "eligible_for_coaching"),
        ([90, 85, 50], "improvement_and_reevaluation"),
        ([80, 65, 49], "improvement_and_reevaluation"),
    ],
)
def test_qualification_rule(scores, expected):
    assert qualify_talent(scores) == expected


@pytest.mark.asyncio
async def test_service_qualification_uses_three_human_scores():
    service = object.__new__(TalentService)
    evaluators = [uuid.uuid4() for _ in range(3)]
    service.get_completed_evaluations = AsyncMock(
        return_value=[
            SimpleNamespace(evaluator_user_id=user_id, overall_score=score)
            for user_id, score in zip(evaluators, [75, 68, 82])
        ]
    )

    result = await service.get_qualification_status(
        application_id=uuid.uuid4()
    )

    assert result == "eligible_for_coaching"
    service.get_completed_evaluations.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_rejects_duplicate_evaluators():
    service = object.__new__(TalentService)
    evaluator = uuid.uuid4()
    service.get_completed_evaluations = AsyncMock(
        return_value=[
            SimpleNamespace(evaluator_user_id=evaluator, overall_score=score)
            for score in [80, 70, 90]
        ]
    )

    with pytest.raises(ValueError, match="distinct"):
        await service.get_qualification_status(
            application_id=uuid.uuid4()
        )
