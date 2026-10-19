"""SMS Talent: controlled recruitment recommendation workflow."""

from dataclasses import dataclass
from typing import Literal

from app.agents.sms_talent_decision import TalentDecision


RecommendationStatus = Literal[
    "not_eligible",
    "awaiting_coach_review",
    "ready_for_recruiter",
]


@dataclass(frozen=True)
class CoachRecommendation:
    athlete_id: str
    coach_id: str
    motivation: str


@dataclass(frozen=True)
class RecruitmentDecision:
    status: RecommendationStatus
    athlete_id: str
    coach_id: str | None = None
    motivation: str | None = None


def prepare_recruitment(
    athlete_id: str,
    talent_decision: TalentDecision,
    recommendation: CoachRecommendation | None = None,
) -> RecruitmentDecision:
    """Require human approval and a motivated SMS coach recommendation."""

    if not athlete_id.strip():
        raise ValueError("Athlete identity is required")

    if talent_decision.status != "eligible_for_coaching":
        return RecruitmentDecision("not_eligible", athlete_id)

    if recommendation is None:
        return RecruitmentDecision("awaiting_coach_review", athlete_id)

    if recommendation.athlete_id != athlete_id:
        raise ValueError("Recommendation belongs to another athlete")

    if not recommendation.coach_id.strip():
        raise ValueError("SMS coach identity is required")

    if not recommendation.motivation.strip():
        raise ValueError("Motivated recommendation is required")

    return RecruitmentDecision(
        status="ready_for_recruiter",
        athlete_id=athlete_id,
        coach_id=recommendation.coach_id,
        motivation=recommendation.motivation,
    )
