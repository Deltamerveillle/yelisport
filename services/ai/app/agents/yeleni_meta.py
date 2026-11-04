"""YELENI Meta: coordination and transparent synthesis of agent outputs."""

from dataclasses import dataclass
from collections.abc import Callable, Mapping
from typing import Literal


Status = Literal["completed", "unavailable", "failed"]


@dataclass(frozen=True)
class AgentResult:
    agent_id: str
    status: Status
    conclusion: str | None = None


@dataclass(frozen=True)
class MetaReport:
    results: tuple[AgentResult, ...]
    completed: int
    unavailable: int
    failed: int
    conflicting_conclusions: bool


def synthesize(results: list[AgentResult]) -> MetaReport:
    """Summarize supplied evidence without generating predictions."""
    ids = [result.agent_id for result in results]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate agent identifiers")

    conclusions = {
        result.conclusion.strip().casefold()
        for result in results
        if result.status == "completed"
        and result.conclusion
        and result.conclusion.strip()
    }

    return MetaReport(
        results=tuple(results),
        completed=sum(r.status == "completed" for r in results),
        unavailable=sum(r.status == "unavailable" for r in results),
        failed=sum(r.status == "failed" for r in results),
        conflicting_conclusions=len(conclusions) > 1,
    )


def orchestrate(
    agents: Mapping[str, Callable[[], str | None]],
) -> MetaReport:
    """Execute registered agents and preserve individual failures."""
    results: list[AgentResult] = []

    for agent_id, execute in agents.items():
        try:
            conclusion = execute()
            if conclusion is None or not conclusion.strip():
                results.append(AgentResult(agent_id, "unavailable"))
            else:
                results.append(
                    AgentResult(agent_id, "completed", conclusion.strip())
                )
        except Exception:
            results.append(AgentResult(agent_id, "failed"))

    return synthesize(results)
