"""
DataQualityAgent — audits all fields and computes a quality score.

Uses the 'data_quality' prompt in batch mode: events are chunked and sent
together to reduce LLM round-trips.  Each chunk produces a single
DataQualityAuditBatch response keyed by source_event_id.

Falls back to rule-based scoring if the LLM is unavailable.
"""

import logging
import time
from typing import Any

from src.agents.base.base_agent import BaseAgent
from src.agents.base.output_models import DataQualityAuditBatch
from src.agents.base.task import AgentResult, AgentTask
from src.agents.llm.provider_router import get_llm_client
from src.agents.registry.prompt_registry import get_prompt_registry

logger = logging.getLogger(__name__)


class DataQualityAgent(BaseAgent):
    """
    Audits event record completeness and flags normalization issues.

    Computes a quality_score (0–1) and populates normalization_errors
    for downstream review.  Processes events in configurable batches
    (default 8).
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
        batch_size = self._config.get("batch_size", 8)
        start = time.monotonic()
        errors: list[str] = []
        total_tokens: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total": 0,
        }
        confidence_scores: dict[str, float] = {}
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
                result: DataQualityAuditBatch = await self._llm.complete_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=DataQualityAuditBatch,
                    temperature=0.0,
                )

                for item in result.items:
                    sid = item.source_event_id
                    idx = event_index.get(sid)
                    if idx is None:
                        continue

                    if not enriched_events[idx].custom_fields:
                        enriched_events[idx].custom_fields = {}
                    enriched_events[idx].data_quality_score = item.quality_score
                    enriched_events[idx].custom_fields["quality_audit"] = {
                        "quality_score": item.quality_score,
                        "missing_fields": item.missing_fields,
                        "normalization_errors": item.normalization_errors,
                        "confidence_flags": item.confidence_flags,
                        "recommendations": item.recommendations,
                    }
                    confidence_scores[sid] = item.quality_score

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
            enriched[i].data_quality_score = round(score, 3)
            enriched[i].custom_fields["quality_audit"] = {
                "quality_score": round(score, 3),
                "missing_fields": [],
                "normalization_errors": [],
                "confidence_flags": {},
                "recommendations": [],
            }
            scores[str(event.source.source_event_id)] = score

        return AgentResult(
            agent_name=self.name,
            prompt_name=self.prompt_name,
            prompt_version="rule-based",
            events=enriched,
            confidence_scores=scores,
            duration_seconds=0.0,
        )
