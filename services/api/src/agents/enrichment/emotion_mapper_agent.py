"""
EmotionMapperAgent — infers emotional outputs and practical access dimensions.

Uses the 'emotion_vibe' prompt in batch mode: events are chunked and sent
together to reduce LLM round-trips.  Each chunk produces a single
EmotionVibeOutputBatch response keyed by source_event_id.
"""

import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from src.agents.base.base_agent import BaseAgent
from src.agents.base.task import AgentResult, AgentTask
from src.agents.llm.provider_router import get_llm_client
from src.agents.registry.prompt_registry import get_prompt_registry

logger = logging.getLogger(__name__)


class EmotionVibeOutput(BaseModel):
    """Structured output from the emotion_vibe prompt (single event)."""

    emotional_output: list[str] = Field(
        default_factory=lambda: ["enjoyment"],
        description="2-4 expected emotions",
    )
    cost_level: str | None = Field(
        default=None,
        description="free | low | medium | high",
    )
    environment: str | None = Field(
        default=None,
        description="indoor | outdoor | digital | mixed",
    )
    risk_level: str | None = Field(
        default=None,
        description="none | very_low | low | medium",
    )
    age_accessibility: str | None = Field(
        default=None,
        description="all | teens+ | adults",
    )
    time_scale: str | None = Field(
        default=None,
        description="short | long | recurring",
    )


class EmotionVibeOutputItem(EmotionVibeOutput):
    """Single-event result inside a batch, keyed by source_event_id."""

    source_event_id: str = Field(
        default="", description="Must match the source_event_id from the input"
    )


class EmotionVibeOutputBatch(BaseModel):
    """Batch output from emotion_mapper agent (one item per input event)."""

    items: list[EmotionVibeOutputItem] = Field(default_factory=list)


class EmotionMapperAgent(BaseAgent):
    """
    Infers emotional outputs and practical access dimensions.

    Fills taxonomy.emotional_output plus practical fields
    (cost_level, environment, risk_level, age_accessibility, time_scale).
    Processes events in configurable batches (default 8).
    """

    name = "emotion_mapper"
    prompt_name = "emotion_vibe"

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._llm = get_llm_client(
            provider=self._config.get("provider", "anthropic"),
            model_name=self._config.get("model", "claude-haiku-4-5-20251001"),
            temperature=self._config.get("temperature", 0.3),
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
                result: EmotionVibeOutputBatch = await self._llm.complete_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=EmotionVibeOutputBatch,
                    temperature=self._config.get("temperature", 0.3),
                )

                for item in result.items:
                    sid = item.source_event_id
                    idx = event_index.get(sid)
                    if idx is None:
                        continue

                    tax = enriched_events[idx].taxonomy_dimension
                    if tax is None:
                        continue

                    if item.emotional_output:
                        tax.emotional_output = item.emotional_output
                    if item.environment:
                        tax.environment = item.environment
                    if item.risk_level:
                        tax.risk_level = item.risk_level
                    if item.age_accessibility:
                        tax.age_accessibility = item.age_accessibility
                    if item.cost_level:
                        tax.cost_level = item.cost_level
                    if item.time_scale:
                        tax.time_scale = item.time_scale
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
