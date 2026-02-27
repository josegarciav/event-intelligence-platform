"""
TaxonomyClassifierAgent — classifies events into the Human Experience Taxonomy.

Uses the 'taxonomy_classification' prompt in batch mode: events are chunked
and sent together to reduce LLM round-trips.  Each chunk produces a single
TaxonomyAttributesExtractionBatch response keyed by source_event_id.
"""

import logging
import time
from typing import Any

from src.agents.base.base_agent import BaseAgent
from src.agents.base.output_models import TaxonomyAttributesExtractionBatch
from src.agents.base.task import AgentResult, AgentTask
from src.agents.llm.provider_router import get_llm_client
from src.agents.registry.prompt_registry import get_prompt_registry

logger = logging.getLogger(__name__)


class TaxonomyClassifierAgent(BaseAgent):
    """
    Classifies events into the Pulsecity Human Experience Taxonomy.

    Fills taxonomy dimension fields: energy_level, social_intensity,
    cognitive_load, physical_involvement, repeatability, emotional_output, etc.
    Processes events in configurable batches (default 8).
    """

    name = "taxonomy_classifier"
    prompt_name = "taxonomy_classification"

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._llm = get_llm_client(
            provider=self._config.get("provider", "anthropic"),
            model_name=self._config.get("model", "claude-haiku-4-5-20251001"),
            temperature=self._config.get("temperature", 0.1),
        )
        self._registry = get_prompt_registry()

    async def run(self, task: AgentTask) -> AgentResult:
        if not self._config.get("enabled", True):
            return AgentResult(
                agent_name=self.name,
                prompt_name=self.prompt_name,
                prompt_version="skipped",
                events=task.events,
                errors=["Agent disabled in config"],
            )

        if not self._llm.is_available:
            logger.warning(f"{self.name}: LLM unavailable, skipping")
            return AgentResult(
                agent_name=self.name,
                prompt_name=self.prompt_name,
                prompt_version="skipped",
                events=task.events,
                errors=["LLM not available — check API key"],
            )

        prompt_version = self._registry.get_active_version(self.prompt_name)
        batch_size = self._config.get("batch_size", 8)
        start = time.monotonic()
        errors: list[str] = []
        total_tokens: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total": 0,
        }
        enriched_events = list(task.events)
        event_index = {
            str(e.source.source_event_id): i for i, e in enumerate(enriched_events)
        }

        for chunk in self._chunk(enriched_events, batch_size):
            batch_ctx = self._build_batch_context(chunk)
            chunk_ids = [str(e.source.source_event_id) for e in chunk]
            try:
                system_prompt, user_prompt = self._registry.render(
                    self.prompt_name,
                    version=task.prompt_version,
                    variables=batch_ctx,
                    agent_name=self.name,
                    batch=True,
                )
                result: TaxonomyAttributesExtractionBatch = (
                    await self._llm.complete_structured(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        output_schema=TaxonomyAttributesExtractionBatch,
                        temperature=self._config.get("temperature", 0.1),
                    )
                )

                for item in result.items:
                    sid = item.source_event_id
                    idx = event_index.get(sid)
                    if idx is None:
                        continue

                    tax = enriched_events[idx].taxonomy_dimension
                    if tax is None:
                        continue

                    if item.energy_level:
                        tax.energy_level = item.energy_level
                    if item.social_intensity:
                        tax.social_intensity = item.social_intensity
                    if item.cognitive_load:
                        tax.cognitive_load = item.cognitive_load
                    if item.physical_involvement:
                        tax.physical_involvement = item.physical_involvement
                    if item.repeatability:
                        tax.repeatability = item.repeatability
                    enriched_events[idx].taxonomy_dimension = tax

                usage = self._llm.get_token_usage()
                for k in total_tokens:
                    total_tokens[k] += usage.get(k, 0)

            except Exception as e:
                msg = f"batch {chunk_ids}: {e}"
                logger.warning(f"{self.name} batch error: {msg}")
                errors.append(msg)

        return AgentResult(
            agent_name=self.name,
            prompt_name=self.prompt_name,
            prompt_version=prompt_version,
            events=enriched_events,
            token_usage=total_tokens,
            errors=errors,
            duration_seconds=time.monotonic() - start,
        )
