"""
BatchEnrichmentRunner — runs the enrichment agent chain on a list of events.

Agent chain (ordered):
  1. feature_alignment   → event_type, tags, event_format
  2. taxonomy_classifier → primary_category, subcategory, behavioral dimensions
  3. emotion_mapper      → emotional_output, cost_level, environment, etc.
  4. data_quality        → quality_score, normalization_errors

Each agent receives the events output by the previous agent (pipeline pattern).
"""

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.schemas.event import EventSchema

from src.agents.base.base_agent import BaseAgent
from src.agents.base.task import AgentResult, AgentTask

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentRunResult:
    """Aggregated result from a full BatchEnrichmentRunner execution."""

    events: list["EventSchema"]
    agent_results: list[AgentResult]
    total_duration_seconds: float
    total_token_usage: dict[str, int] = field(default_factory=dict)
    errors_by_agent: dict[str, list[str]] = field(default_factory=dict)
    prompt_versions_used: dict[str, str] = field(default_factory=dict)

    @property
    def total_errors(self) -> int:
        return sum(len(errs) for errs in self.errors_by_agent.values())

    @property
    def success(self) -> bool:
        return len(self.events) > 0


class BatchEnrichmentRunner:
    """
    Runs the ordered enrichment agent chain on a batch of events.

    The chain is configured via agents.yaml and instantiated through AgentRegistry.
    Each agent's output events feed into the next agent.
    """

    def __init__(
        self,
        agents_config: dict[str, Any] | None = None,
    ):
        """
        Args:
            agents_config: Full agents.yaml config dict. If None, defaults are used.
        """
        self._agents_config = agents_config or {}
        self._agent_chain: list[BaseAgent] = self._build_chain()

    def _build_chain(self) -> list[BaseAgent]:
        """Instantiate the ordered agent chain from config."""
        from src.agents.registry.agent_registry import AgentRegistry

        registry = AgentRegistry()
        agents_section = self._agents_config.get("agents", {})

        # Ordered chain — must match the plan
        chain_order = [
            "feature_alignment",
            "taxonomy_classifier",
            "emotion_mapper",
            "data_quality",
            "deduplication",
        ]

        chain: list[BaseAgent] = []
        for agent_name in chain_order:
            agent_config = agents_section.get(agent_name, {})
            if not agent_config.get("enabled", True):
                logger.info(
                    f"BatchEnrichmentRunner: skipping disabled agent '{agent_name}'"
                )
                continue
            try:
                agent = registry.get(agent_name, agent_config)
                chain.append(agent)
                logger.debug(f"BatchEnrichmentRunner: registered agent '{agent_name}'")
            except Exception as e:
                logger.warning(
                    f"BatchEnrichmentRunner: failed to load agent '{agent_name}': {e}"
                )

        return chain

    async def run(
        self,
        events: list["EventSchema"],
        prompt_version: str = "active",
    ) -> EnrichmentRunResult:
        """
        Run the full agent chain on a batch of events.

        Args:
            events: EventSchema objects to enrich
            prompt_version: "active" or explicit version (e.g., "v1")

        Returns:
            EnrichmentRunResult with enriched events and per-agent metadata
        """
        if not events:
            return EnrichmentRunResult(
                events=[],
                agent_results=[],
                total_duration_seconds=0.0,
            )

        start = time.monotonic()
        current_events = list(events)
        agent_results: list[AgentResult] = []
        total_tokens: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total": 0,
        }
        errors_by_agent: dict[str, list[str]] = {}
        prompt_versions_used: dict[str, str] = {}

        for agent in self._agent_chain:
            task = AgentTask(
                agent_name=agent.name,
                events=current_events,
                target_fields=[],  # each agent knows its own target fields
                prompt_version=prompt_version,
            )
            try:
                logger.info(
                    f"BatchEnrichmentRunner: running {agent.name} on {len(current_events)} events"
                )
                result = await agent.run(task)
                agent_results.append(result)

                # Pipeline — pass enriched events to next agent
                current_events = result.events

                # Aggregate metadata
                for k in total_tokens:
                    total_tokens[k] += result.token_usage.get(k, 0)
                if result.errors:
                    errors_by_agent[agent.name] = result.errors
                prompt_versions_used[agent.name] = result.prompt_version

            except Exception as e:
                msg = f"Agent '{agent.name}' raised an exception: {e}"
                logger.error(msg, exc_info=True)
                errors_by_agent[agent.name] = [msg]

        return EnrichmentRunResult(
            events=current_events,
            agent_results=agent_results,
            total_duration_seconds=time.monotonic() - start,
            total_token_usage=total_tokens,
            errors_by_agent=errors_by_agent,
            prompt_versions_used=prompt_versions_used,
        )
