import pytest

from app.agents.sms_talent_decision import evaluate_human_scores


@pytest.mark.parametrize("scores", [
    [51, 51, 51],
    [50.01, 65, 90],
    [100, 100, 100],
])
def test_three_scores_above_50_qualify(scores):
    assert evaluate_human_scores(scores).status == "eligible_for_coaching"


@pytest.mark.parametrize("scores", [
    [90, 85, 50],
    [100, 100, 49],
    [50, 50, 50],
])
def test_one_score_at_or_below_50_prevents_qualification(scores):
    assert evaluate_human_scores(scores).status == "not_approved"


def test_incomplete_evaluations_remain_pending():
    assert evaluate_human_scores([80, 90]).status == "awaiting_human_evaluations"
    assert evaluate_human_scores([80, None, 90]).status == "awaiting_human_evaluations"


@pytest.mark.parametrize("scores", [
    [-1, 80, 90],
    [101, 80, 90],
    ["invalid", 80, 90],
    [float("nan"), 80, 90],
    [True, 80, 90],
    [80, 90, 95, 99],
])
def test_invalid_scores_are_rejected(scores):
    with pytest.raises(ValueError):
        evaluate_human_scores(scores)
