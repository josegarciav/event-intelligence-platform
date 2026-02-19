"""
TaxonomyClassifierAgent — classifies events into the Human Experience Taxonomy.

Uses the 'taxonomy_classification' prompt to fill:
primary_category, subcategory, activity_id, energy_level, social_intensity,
cognitive_load, physical_involvement, repeatability.
"""

import logging
import time
from typing import Any

from src.agents.base.base_agent import BaseAgent
from src.agents.base.output_models import TaxonomyAttributesExtraction
from src.agents.base.task import AgentResult, AgentTask
from src.agents.llm.provider_router import get_llm_client
from src.agents.registry.prompt_registry import get_prompt_registry

logger = logging.getLogger(__name__)


class TaxonomyClassifierAgent(BaseAgent):
    """
    Classifies events into the Pulsecity Human Experience Taxonomy.

    Fills taxonomy dimension fields: primary_category, subcategory,
    energy_level, social_intensity, cognitive_load, physical_involvement,
    repeatability.
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
        start = time.monotonic()
        errors: list[str] = []
        total_tokens: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total": 0,
        }
        enriched_events = list(task.events)

        for i, event in enumerate(enriched_events):
            ctx = self._build_event_context(event)
            if not ctx.get("title"):
                continue

            try:
                system_prompt, user_prompt = self._registry.render(
                    self.prompt_name,
                    version=task.prompt_version,
                    variables=ctx,
                    agent_name=self.name,
                    event_id=str(event.source_event_id),
                )
                result: TaxonomyAttributesExtraction = (
                    await self._llm.complete_structured(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        output_schema=TaxonomyAttributesExtraction,
                        temperature=self._config.get("temperature", 0.1),
                    )
                )
                # Apply to taxonomy dimension
                if event.taxonomy:
                    tax = event.taxonomy
                    if result.energy_level:
                        tax.energy_level = result.energy_level
                    if result.social_intensity:
                        tax.social_intensity = result.social_intensity
                    if result.cognitive_load:
                        tax.cognitive_load = result.cognitive_load
                    if result.physical_involvement:
                        tax.physical_involvement = result.physical_involvement
                    if result.environment:
                        tax.environment = result.environment
                    if result.risk_level:
                        tax.risk_level = result.risk_level
                    if result.age_accessibility:
                        tax.age_accessibility = result.age_accessibility
                    if result.repeatability:
                        tax.repeatability = result.repeatability
                    if result.emotional_output:
                        tax.emotional_output = result.emotional_output
                    enriched_events[i].taxonomy = tax

                usage = self._llm.get_token_usage()
                for k in total_tokens:
                    total_tokens[k] += usage.get(k, 0)

            except Exception as e:
                msg = f"event={event.source_event_id}: {e}"
                logger.warning(f"{self.name} error: {msg}")
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
