"""Regression tests for YELENI Meta."""

import pytest

from app.agents.yeleni_meta import AgentResult, orchestrate, synthesize


def test_synthesis_detects_different_conclusions():
    report = synthesize([
        AgentResult("a", "completed", "A"),
        AgentResult("b", "completed", "B"),
    ])
    assert report.completed == 2
    assert report.conflicting_conclusions


def test_duplicate_agents_are_rejected():
    with pytest.raises(ValueError):
        synthesize([
            AgentResult("a", "completed", "A"),
            AgentResult("a", "completed", "B"),
        ])


def test_orchestration_isolates_failures():
    def failing_agent():
        raise RuntimeError("Simulated failure")

    report = orchestrate({
        "statistics": lambda: "A",
        "tactics": lambda: "B",
        "form": lambda: None,
        "external": failing_agent,
    })

    assert report.completed == 2
    assert report.unavailable == 1
    assert report.failed == 1
    assert report.conflicting_conclusions


def test_no_results_does_not_invent_conclusions():
    report = synthesize([])
    assert report.completed == 0
    assert not report.conflicting_conclusions
