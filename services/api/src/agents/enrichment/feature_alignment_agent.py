"""
FeatureAlignmentAgent — restructured from the former feature_extractor.py.

Fills in event_type, tags, and event_format using the core_metadata prompt.
Targets fields that are deterministic from title + description.
"""

import logging
import time
from typing import Any

from src.agents.base.base_agent import BaseAgent
from src.agents.base.output_models import MissingFieldsExtraction
from src.agents.base.task import AgentResult, AgentTask
from src.agents.llm.provider_router import get_llm_client
from src.agents.registry.prompt_registry import get_prompt_registry

logger = logging.getLogger(__name__)


class FeatureAlignmentAgent(BaseAgent):
    """
    Fills core metadata fields: event_type, tags, event_format.

    Uses the 'core_metadata' prompt. Gracefully skips if LLM is unavailable.
    """

    name = "feature_alignment"
    prompt_name = "core_metadata"

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
            logger.warning(f"{self.name}: LLM unavailable, skipping enrichment")
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
                result: MissingFieldsExtraction = await self._llm.complete_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=MissingFieldsExtraction,
                    temperature=self._config.get("temperature", 0.1),
                )
                # Apply extracted fields
                if result.event_type and not event.event_type:
                    from src.schemas.event import EventType

                    try:
                        enriched_events[i].event_type = EventType(result.event_type)
                    except ValueError:
                        pass
                if result.tags:
                    existing = set(event.tags or [])
                    enriched_events[i].tags = list(existing | set(result.tags))
                if result.event_format and not event.event_format:
                    from src.schemas.event import EventFormat

                    try:
                        enriched_events[i].event_format = EventFormat(
                            result.event_format
                        )
                    except ValueError:
                        pass

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
