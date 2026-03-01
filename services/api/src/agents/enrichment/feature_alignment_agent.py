"""
FeatureAlignmentAgent — fills event_type, tags, and event_format.

Uses the 'feature_alignment' prompt in batch mode: events are chunked and sent
to the LLM together to save on round-trip latency.  Each chunk produces a
single structured response (MissingFieldsExtractionBatch) with one item per
event, keyed by source_event_id.
"""

import logging
import time
from typing import Any

from src.agents.base.base_agent import BaseAgent
from src.agents.base.output_models import MissingFieldsExtractionBatch
from src.agents.base.task import AgentResult, AgentTask
from src.agents.llm.provider_router import get_llm_client
from src.agents.registry.prompt_registry import get_prompt_registry

logger = logging.getLogger(__name__)


class FeatureAlignmentAgent(BaseAgent):
    """
    Fills core metadata fields: event_type, tags, event_format.

    Processes events in configurable batches (default 8) to reduce LLM
    round-trips.  Gracefully skips if LLM is unavailable.
    """

    name = "feature_alignment"
    prompt_name = "feature_alignment"

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
        batch_size = self._config.get("batch_size", 8)
        start = time.monotonic()
        errors: list[str] = []
        total_tokens: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total": 0,
        }
        enriched_events = list(task.events)
        # Build an index so we can apply results back by source_event_id
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
                result: MissingFieldsExtractionBatch = (
                    await self._llm.complete_structured(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        output_schema=MissingFieldsExtractionBatch,
                        temperature=self._config.get("temperature", 0.1),
                    )
                )

                for item in result.items:
                    sid = item.source_event_id
                    idx = event_index.get(sid)
                    if idx is None:
                        continue

                    event = enriched_events[idx]
                    if item.event_type and not event.event_type:
                        from src.schemas.event import EventType

                        try:
                            enriched_events[idx].event_type = EventType(item.event_type)
                        except ValueError:
                            pass
                    if item.tags:
                        existing = set(event.tags or [])
                        enriched_events[idx].tags = list(existing | set(item.tags))
                    if item.event_format and not event.format:
                        from src.schemas.event import EventFormat

                        try:
                            enriched_events[idx].format = EventFormat(
                                item.event_format
                            )
                        except ValueError:
                            pass

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
