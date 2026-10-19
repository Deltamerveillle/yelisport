"""Tests for SMS Talent human-only eligibility decisions."""

from dataclasses import replace

from app.agents.sms_talent_decision import evaluate_talent
from app.agents.triple_vision import (
    AI_SLOTS,
    ALL_SLOTS,
    Evaluation,
)


def make_evaluations(human_votes=None, ai_conclusions=None):
    human_votes = human_votes or {}
    ai_conclusions = ai_conclusions or {}
    items = []

    for slot in ALL_SLOTS:
        if slot in AI_SLOTS:
            conclusion = ai_conclusions.get(slot)
            items.append(
                Evaluation(
                    slot_id=slot,
                    source="ai",
                    status="completed" if conclusion else "pending",
                    conclusion=conclusion,
                    evaluator_id=slot if conclusion else None,
                )
            )
        else:
            vote = human_votes.get(slot)
            items.append(
                Evaluation(
                    slot_id=slot,
                    source="human",
                    status="completed" if vote else "pending",
                    conclusion=vote,
                    evaluator_id=f"expert_{slot}" if vote else None,
                )
            )

    return items


def test_three_favorable_humans_unlock_coaching():
    votes = {f"human_{i}": "favorable" for i in range(1, 4)}
    decision = evaluate_talent(make_evaluations(votes))
    assert decision.status == "eligible_for_coaching"
    assert decision.favorable_votes == 3


def test_one_unfavorable_human_blocks_coaching():
    votes = {
        "human_1": "favorable",
        "human_2": "defavorable",
        "human_3": "favorable",
    }
    decision = evaluate_talent(make_evaluations(votes))
    assert decision.status == "not_approved"


def test_missing_human_evaluation_prevents_approval():
    votes = {"human_1": "favorable", "human_2": "favorable"}
    decision = evaluate_talent(make_evaluations(votes))
    assert decision.status == "awaiting_human_evaluations"


def test_unfavorable_ai_cannot_block_unanimous_humans():
    votes = {f"human_{i}": "favorable" for i in range(1, 4)}
    ai = {f"ai_{i}": "Evaluation tres defavorable" for i in range(1, 4)}
    decision = evaluate_talent(make_evaluations(votes, ai))
    assert decision.status == "eligible_for_coaching"


def test_favorable_ai_cannot_override_human_refusal():
    votes = {
        "human_1": "favorable",
        "human_2": "defavorable",
        "human_3": "favorable",
    }
    ai = {f"ai_{i}": "Excellent potentiel" for i in range(1, 4)}
    decision = evaluate_talent(make_evaluations(votes, ai))
    assert decision.status == "not_approved"


def test_no_human_votes_means_waiting():
    decision = evaluate_talent(make_evaluations())
    assert decision.status == "awaiting_human_evaluations"
