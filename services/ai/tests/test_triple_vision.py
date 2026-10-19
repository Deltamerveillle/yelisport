"""Tests for SMS Triple Vision evaluation contracts."""

import pytest

from app.agents.triple_vision import (
    ALL_SLOTS,
    AI_SLOTS,
    Evaluation,
    validate_evaluations,
)


def make_pending():
    return [
        Evaluation(
            slot_id=slot,
            source="ai" if slot in AI_SLOTS else "human",
            status="pending",
        )
        for slot in ALL_SLOTS
    ]


def test_six_pending_slots_are_valid():
    validate_evaluations(make_pending())


def test_missing_slot_is_rejected():
    with pytest.raises(ValueError):
        validate_evaluations(make_pending()[:-1])


def test_duplicate_slot_is_rejected():
    items = make_pending()
    items[-1] = items[0]
    with pytest.raises(ValueError):
        validate_evaluations(items)


def test_human_slot_cannot_be_ai():
    items = make_pending()
    items[-1] = Evaluation("human_3", "ai", "pending")
    with pytest.raises(ValueError):
        validate_evaluations(items)


def test_completed_result_requires_identity():
    items = make_pending()
    items[0] = Evaluation("ai_1", "ai", "completed", "A")
    with pytest.raises(ValueError):
        validate_evaluations(items)


def test_pending_result_cannot_claim_conclusion():
    items = make_pending()
    items[0] = Evaluation("ai_1", "ai", "pending", "A")
    with pytest.raises(ValueError):
        validate_evaluations(items)


def test_human_evaluators_must_be_distinct():
    items = make_pending()
    items[3] = Evaluation("human_1", "human", "completed", "A", "expert_1")
    items[4] = Evaluation("human_2", "human", "completed", "B", "expert_1")
    with pytest.raises(ValueError):
        validate_evaluations(items)


def test_three_distinct_human_evaluations_are_valid():
    items = make_pending()
    for i in range(3):
        items[i + 3] = Evaluation(
            f"human_{i + 1}",
            "human",
            "completed",
            f"Analyse {i + 1}",
            f"expert_{i + 1}",
        )
    validate_evaluations(items)
