"""
DataQualityAgent — audits all fields and computes a quality score.

Uses the 'data_quality' prompt. Does not modify event fields directly —
writes quality_score and normalization_errors into event metadata.
"""

import json
import logging
import time
from typing import Any

from src.agents.base.base_agent import BaseAgent
from src.agents.base.output_models import DataQualityAudit
from src.agents.base.task import AgentResult, AgentTask
from src.agents.llm.provider_router import get_llm_client
from src.agents.registry.prompt_registry import get_prompt_registry

logger = logging.getLogger(__name__)


class DataQualityAgent(BaseAgent):
    """
    Audits event record completeness and flags normalization issues.

    Computes a quality_score (0–1) and populates normalization_errors
    in the event's custom_fields for downstream review.
    """

    name = "data_quality"
    prompt_name = "data_quality"

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._llm = get_llm_client(
            provider=self._config.get("provider", "anthropic"),
            model_name=self._config.get("model", "claude-haiku-4-5-20251001"),
            temperature=0.0,  # deterministic — always 0 for quality audits
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
            logger.warning(
                f"{self.name}: LLM unavailable, using rule-based quality scoring"
            )
            return self._rule_based_quality(task)

        prompt_version = self._registry.get_active_version(self.prompt_name)
        start = time.monotonic()
        errors: list[str] = []
        total_tokens: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total": 0,
        }
        confidence_scores: dict[str, float] = {}
        enriched_events = list(task.events)

        for i, event in enumerate(enriched_events):
            try:
                # Serialize event for prompt
                event_dict = event.model_dump()
                event_json = json.dumps(event_dict, default=str, indent=2)[
                    :3000
                ]  # cap for token budget

                system_prompt, user_prompt = self._registry.render(
                    self.prompt_name,
                    version=task.prompt_version,
                    variables={"event_json": event_json},
                    agent_name=self.name,
                    event_id=str(event.source_event_id),
                )
                result: DataQualityAudit = await self._llm.complete_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=DataQualityAudit,
                    temperature=0.0,
                )

                # Write quality data into custom_fields
                if not enriched_events[i].custom_fields:
                    enriched_events[i].custom_fields = {}
                enriched_events[i].custom_fields["quality_score"] = result.quality_score
                enriched_events[i].custom_fields[
                    "normalization_errors"
                ] = result.normalization_errors
                enriched_events[i].custom_fields[
                    "missing_fields_audit"
                ] = result.missing_fields

                # Track per-field confidence
                event_id = str(event.source_event_id)
                confidence_scores[event_id] = result.quality_score

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
            confidence_scores=confidence_scores,
            token_usage=total_tokens,
            errors=errors,
            duration_seconds=time.monotonic() - start,
        )

    def _rule_based_quality(self, task: AgentTask) -> AgentResult:
        """Rule-based quality scoring fallback when LLM is unavailable."""
        enriched = list(task.events)
        scores: dict[str, float] = {}

        critical_fields = [
            "title",
            "source_event_id",
            "start_datetime",
            "city",
            "source_url",
        ]
        enrichment_fields = ["description", "venue_name", "event_type", "tags"]

        for i, event in enumerate(enriched):
            event_dict = event.model_dump()
            critical_present = sum(1 for f in critical_fields if event_dict.get(f))
            enrichment_present = sum(1 for f in enrichment_fields if event_dict.get(f))

            score = (critical_present / len(critical_fields)) * 0.7 + (
                enrichment_present / len(enrichment_fields)
            ) * 0.3
            if not enriched[i].custom_fields:
                enriched[i].custom_fields = {}
            enriched[i].custom_fields["quality_score"] = round(score, 3)
            scores[str(event.source_event_id)] = score

        return AgentResult(
            agent_name=self.name,
            prompt_name=self.prompt_name,
            prompt_version="rule-based",
            events=enriched,
            confidence_scores=scores,
            duration_seconds=0.0,
        )
