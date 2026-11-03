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


def evaluate_human_scores(scores: list) -> TalentDecision:
    """Determine SMS coaching eligibility from three human scores only."""
    from decimal import Decimal, InvalidOperation

    if len(scores) > 3:
        raise ValueError("Exactly three human evaluations are allowed")

    favorable = 0

    for score in scores:
        if score is None:
            continue

        if isinstance(score, bool):
            raise ValueError("Invalid evaluation score")

        try:
            value = Decimal(str(score))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("Invalid evaluation score") from None

        if not value.is_finite() or not Decimal("0") <= value <= Decimal("100"):
            raise ValueError("Evaluation score must be between 0 and 100")

        if value > Decimal("50"):
            favorable += 1

    if len(scores) < 3 or any(score is None for score in scores):
        status = "awaiting_human_evaluations"
    elif favorable == 3:
        status = "eligible_for_coaching"
    else:
        status = "not_approved"

    return TalentDecision(status=status, favorable_votes=favorable)
