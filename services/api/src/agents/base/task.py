"""
AgentTask and AgentResult dataclasses for the enrichment pipeline.

AgentTask describes a unit of work given to a BaseAgent.
AgentResult is the structured output returned by the agent.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.schemas.event import EventSchema


@dataclass
class AgentTask:
    """Describes a unit of enrichment work for a single agent."""

    agent_name: str
    events: list["EventSchema"]
    target_fields: list[str]  # which EventSchema fields this agent is responsible for
    prompt_version: str = "active"  # "active" | "v1" | "v2" etc.
    priority: int = 1
    retry_limit: int = 2
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Structured output returned by a BaseAgent after processing a task."""

    agent_name: str
    prompt_name: str
    prompt_version: str  # resolved version actually used
    events: list["EventSchema"]  # enriched event list
    confidence_scores: dict[str, float] = field(default_factory=dict)  # field → score
    token_usage: dict[str, int] = field(
        default_factory=dict
    )  # prompt_tokens, completion_tokens, total
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
