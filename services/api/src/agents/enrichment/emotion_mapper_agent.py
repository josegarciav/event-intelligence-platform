"""
EmotionMapperAgent — infers emotional outputs and practical access dimensions.

Uses the 'emotion_vibe' prompt to fill:
emotional_output, cost_level, environment, risk_level, age_accessibility, time_scale.
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
    """Structured output from the emotion_vibe prompt."""

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


class EmotionMapperAgent(BaseAgent):
    """
    Infers emotional outputs and practical access dimensions.

    Fills taxonomy.emotional_output plus practical fields
    (cost_level, environment, risk_level, age_accessibility, time_scale).
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

            ctx["price_raw_text"] = str(event.price.cost or "") if event.price else ""
            ctx["artists"] = ", ".join(ctx.get("artists", [])) if isinstance(ctx.get("artists"), list) else ""

            try:
                system_prompt, user_prompt = self._registry.render(
                    self.prompt_name,
                    version=task.prompt_version,
                    variables=ctx,
                    agent_name=self.name,
                    event_id=str(event.source_event_id),
                )
                result: EmotionVibeOutput = await self._llm.complete_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=EmotionVibeOutput,
                    temperature=self._config.get("temperature", 0.3),
                )

                # Apply emotional outputs to taxonomy
                if event.taxonomy and result.emotional_output:
                    enriched_events[i].taxonomy.emotional_output = result.emotional_output  # type: ignore[union-attr]
                if event.taxonomy and result.environment:
                    enriched_events[i].taxonomy.environment = result.environment  # type: ignore[union-attr]
                if event.taxonomy and result.risk_level:
                    enriched_events[i].taxonomy.risk_level = result.risk_level  # type: ignore[union-attr]
                if event.taxonomy and result.age_accessibility:
                    enriched_events[i].taxonomy.age_accessibility = result.age_accessibility  # type: ignore[union-attr]
                if event.taxonomy and result.repeatability if hasattr(result, "repeatability") else False:
                    pass  # repeatability is on taxonomy; handled by taxonomy agent

                # Apply cost_level and time_scale to taxonomy
                if event.taxonomy and result.cost_level:
                    enriched_events[i].taxonomy.cost_level = result.cost_level  # type: ignore[union-attr]
                if event.taxonomy and result.time_scale:
                    enriched_events[i].taxonomy.time_scale = result.time_scale  # type: ignore[union-attr]

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
