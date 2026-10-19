"""Tests for SMS Talent recruitment workflow."""

import pytest

from app.agents.sms_talent_decision import TalentDecision
from app.agents.sms_talent_recruitment import (
    CoachRecommendation,
    prepare_recruitment,
)


def approved():
    return TalentDecision("eligible_for_coaching", 3)


def rejected():
    return TalentDecision("not_approved", 2)


def recommendation():
    return CoachRecommendation(
        athlete_id="athlete_001",
        coach_id="coach_sms_001",
        motivation="Potentiel technique et progression confirmes.",
    )


def test_approved_athlete_waits_for_coach():
    result = prepare_recruitment("athlete_001", approved())
    assert result.status == "awaiting_coach_review"


def test_rejected_athlete_cannot_be_recommended():
    result = prepare_recruitment(
        "athlete_001", rejected(), recommendation()
    )
    assert result.status == "not_eligible"


def test_coach_can_prepare_motivated_recommendation():
    result = prepare_recruitment(
        "athlete_001", approved(), recommendation()
    )
    assert result.status == "ready_for_recruiter"
    assert result.coach_id == "coach_sms_001"
    assert result.motivation


def test_recommendation_for_another_athlete_is_rejected():
    with pytest.raises(ValueError):
        prepare_recruitment(
            "athlete_002", approved(), recommendation()
        )


def test_missing_coach_identity_is_rejected():
    item = CoachRecommendation(
        "athlete_001", "", "Motivation valide"
    )
    with pytest.raises(ValueError):
        prepare_recruitment("athlete_001", approved(), item)


def test_missing_motivation_is_rejected():
    item = CoachRecommendation(
        "athlete_001", "coach_sms_001", " "
    )
    with pytest.raises(ValueError):
        prepare_recruitment("athlete_001", approved(), item)


def test_missing_athlete_identity_is_rejected():
    with pytest.raises(ValueError):
        prepare_recruitment("", approved(), recommendation())
