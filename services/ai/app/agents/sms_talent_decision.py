"""SMS Talent: human expertise determines coaching eligibility."""

from dataclasses import dataclass
from typing import Literal

from app.agents.triple_vision import (
    Evaluation,
    HUMAN_SLOTS,
    validate_evaluations,
)


DecisionStatus = Literal[
    "eligible_for_coaching",
    "not_approved",
    "awaiting_human_evaluations",
]


@dataclass(frozen=True)
class TalentDecision:
    status: DecisionStatus
    favorable_votes: int
    required_votes: int = 3


def evaluate_talent(evaluations: list[Evaluation]) -> TalentDecision:
    """Require three favorable human decisions for SMS coaching."""

    validate_evaluations(evaluations)

    humans = [
        item for item in evaluations
        if item.slot_id in HUMAN_SLOTS
    ]

    completed = [
        item for item in humans
        if item.status == "completed"
    ]

    favorable = sum(
        item.conclusion.strip().casefold() == "favorable"
        for item in completed
    )

    if len(completed) < 3:
        status = "awaiting_human_evaluations"
    elif favorable == 3:
        status = "eligible_for_coaching"
    else:
        status = "not_approved"

    return TalentDecision(
        status=status,
        favorable_votes=favorable,
    )
