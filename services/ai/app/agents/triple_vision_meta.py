"""YELENI Meta supervises AI evaluations only."""

from app.agents.triple_vision import (
    AI_SLOTS,
    Evaluation,
    validate_evaluations,
)
from app.agents.yeleni_meta import (
    AgentResult,
    MetaReport,
    synthesize,
)


def build_ai_meta_report(
    evaluations: list[Evaluation],
) -> MetaReport:
    """Summarize the three AI evaluations without managing humans."""

    validate_evaluations(evaluations)

    results = []

    for item in evaluations:
        if item.slot_id not in AI_SLOTS:
            continue

        if item.status == "completed":
            results.append(
                AgentResult(
                    agent_id=item.slot_id,
                    status="completed",
                    conclusion=item.conclusion,
                )
            )
        else:
            results.append(
                AgentResult(
                    agent_id=item.slot_id,
                    status="unavailable",
                )
            )

    return synthesize(results)
