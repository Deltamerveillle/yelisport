"""SMS Triple Vision: six distinct, verifiable evaluation slots."""

from dataclasses import dataclass
from typing import Literal


EvaluationStatus = Literal["pending", "completed", "unavailable"]
EvaluationSource = Literal["ai", "human"]


@dataclass(frozen=True)
class Evaluation:
    slot_id: str
    source: EvaluationSource
    status: EvaluationStatus
    conclusion: str | None = None
    evaluator_id: str | None = None


AI_SLOTS = ("ai_1", "ai_2", "ai_3")
HUMAN_SLOTS = ("human_1", "human_2", "human_3")
ALL_SLOTS = AI_SLOTS + HUMAN_SLOTS


def validate_evaluations(evaluations: list[Evaluation]) -> None:
    """Validate slot identity and evidence; never fill missing results."""
    ids = [item.slot_id for item in evaluations]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate evaluation slots")

    if set(ids) != set(ALL_SLOTS):
        raise ValueError("Triple Vision requires exactly six slots")

    human_evaluators = []

    for item in evaluations:
        expected_source = "ai" if item.slot_id in AI_SLOTS else "human"

        if item.source != expected_source:
            raise ValueError("Incorrect evaluation source")

        if item.status == "completed":
            if not item.conclusion or not item.conclusion.strip():
                raise ValueError("Completed evaluation requires a conclusion")
            if not item.evaluator_id or not item.evaluator_id.strip():
                raise ValueError("Completed evaluation requires evaluator identity")
        elif item.conclusion is not None:
            raise ValueError("Incomplete evaluation cannot claim a conclusion")

        if item.source == "human" and item.status == "completed":
            human_evaluators.append(item.evaluator_id.strip())

    if len(human_evaluators) != len(set(human_evaluators)):
        raise ValueError("Human evaluations must have distinct evaluators")
